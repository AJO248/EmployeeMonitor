#include <windows.h>
#include <string>
#include <winsock2.h>
#include <windows.h>
#include <ws2tcpip.h>
#include <string>
#include <iostream>
#include <thread>
#include <vector>
#include <sstream>
#include <iomanip>
#include <chrono>
#include <mutex>
#include <sqlite3.h>

// Minimal SHA1 + base64 implementations for WebSocket handshake
// NOTE: lightweight implementations adapted for brevity.

static std::string base64_encode(const unsigned char *data, size_t len)
{
    static const char *table = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/";
    std::string out;
    int val = 0, valb = -6;
    for (size_t i = 0; i < len; ++i)
    {
        val = (val << 8) + data[i];
        valb += 8;
        while (valb >= 0)
        {
            out.push_back(table[(val >> valb) & 0x3F]);
            valb -= 6;
        }
    }
    if (valb > -6)
        out.push_back(table[((val << 8) >> (valb + 8)) & 0x3F]);
    while (out.size() % 4)
        out.push_back('=');
    return out;
}

// Simple SHA1 using Windows CryptoAPI for correctness
static std::string sha1_base64(const std::string &input)
{
    HCRYPTPROV hProv = 0;
    HCRYPTHASH hHash = 0;
    std::string result;
    if (!CryptAcquireContextW(&hProv, NULL, NULL, PROV_RSA_FULL, CRYPT_VERIFYCONTEXT))
        return result;
    if (!CryptCreateHash(hProv, CALG_SHA1, 0, 0, &hHash))
    {
        CryptReleaseContext(hProv, 0);
        return result;
    }
    CryptHashData(hHash, reinterpret_cast<const BYTE *>(input.data()), (DWORD)input.size(), 0);
    BYTE digest[20];
    DWORD digestLen = sizeof(digest);
    if (CryptGetHashParam(hHash, HP_HASHVAL, digest, &digestLen, 0))
    {
        result = base64_encode(digest, digestLen);
    }
    CryptDestroyHash(hHash);
    CryptReleaseContext(hProv, 0);
    return result;
}

std::mutex db_mutex;

static sqlite3 *db = nullptr;

bool init_db(const char *path)
{
    std::lock_guard<std::mutex> lg(db_mutex);
    if (sqlite3_open(path, &db) != SQLITE_OK)
        return false;
    const char *sql = "CREATE TABLE IF NOT EXISTS events (id INTEGER PRIMARY KEY, raw TEXT, received_at INTEGER);";
    char *err = nullptr;
    int rc = sqlite3_exec(db, sql, nullptr, nullptr, &err);
    if (rc != SQLITE_OK)
    {
        if (err)
            sqlite3_free(err);
        return false;
    }
    return true;
}

void insert_raw_event(const std::string &raw)
{
    std::lock_guard<std::mutex> lg(db_mutex);
    if (!db)
        return;
    const char *sql = "INSERT INTO events (raw, received_at) VALUES (?, ?);";
    sqlite3_stmt *stmt = nullptr;
    if (sqlite3_prepare_v2(db, sql, -1, &stmt, nullptr) != SQLITE_OK)
        return;
    sqlite3_bind_text(stmt, 1, raw.c_str(), (int)raw.size(), SQLITE_TRANSIENT);
    sqlite3_bind_int64(stmt, 2, (sqlite3_int64)std::chrono::system_clock::to_time_t(std::chrono::system_clock::now()));
    sqlite3_step(stmt);
    sqlite3_finalize(stmt);
}

std::string read_http_header(SOCKET s)
{
    std::string header;
    char buf[1024];
    int n;
    while ((n = recv(s, buf, sizeof(buf), 0)) > 0)
    {
        header.append(buf, buf + n);
        if (header.find("\r\n\r\n") != std::string::npos)
            break;
    }
    return header;
}

std::string get_header_value(const std::string &headers, const std::string &key)
{
    std::string k = key + ": ";
    auto pos = headers.find(k);
    if (pos == std::string::npos)
        return {};
    pos += k.size();
    auto end = headers.find('\r', pos);
    if (end == std::string::npos)
        end = headers.find('\n', pos);
    return headers.substr(pos, end - pos);
}

void ws_send_handshake(SOCKET client, const std::string &accept)
{
    std::ostringstream resp;
    resp << "HTTP/1.1 101 Switching Protocols\r\n"
         << "Upgrade: websocket\r\n"
         << "Connection: Upgrade\r\n"
         << "Sec-WebSocket-Accept: " << accept << "\r\n\r\n";
    std::string s = resp.str();
    send(client, s.c_str(), (int)s.size(), 0);
}

// Read a single WebSocket text frame and return payload
std::string ws_read_frame(SOCKET client)
{
    uint8_t hdr[2];
    int n = recv(client, (char *)hdr, 2, 0);
    if (n <= 0)
        return {};
    bool fin = (hdr[0] & 0x80) != 0;
    uint8_t opcode = hdr[0] & 0x0f;
    bool masked = (hdr[1] & 0x80) != 0;
    uint64_t payload_len = hdr[1] & 0x7f;
    if (payload_len == 126)
    {
        uint8_t ext[2];
        recv(client, (char *)ext, 2, 0);
        payload_len = (ext[0] << 8) | ext[1];
    }
    else if (payload_len == 127)
    {
        uint8_t ext[8];
        recv(client, (char *)ext, 8, 0);
        payload_len = 0;
        for (int i = 0; i < 8; ++i)
            payload_len = (payload_len << 8) | ext[i];
    }
    uint8_t mask[4] = {0, 0, 0, 0};
    if (masked)
        recv(client, (char *)mask, 4, 0);
    std::string payload;
    payload.resize(payload_len);
    size_t received = 0;
    while (received < payload_len)
    {
        int chunk = recv(client, &payload[received], (int)(payload_len - received), 0);
        if (chunk <= 0)
            break;
        received += chunk;
    }
    if (masked)
    {
        for (size_t i = 0; i < payload.size(); ++i)
            payload[i] ^= mask[i % 4];
    }
    return payload;
}

void ws_server_thread()
{
    WSADATA wsaData;
    WSAStartup(MAKEWORD(2, 2), &wsaData);
    SOCKET listenSock = socket(AF_INET, SOCK_STREAM, IPPROTO_TCP);
    sockaddr_in addr{};
    addr.sin_family = AF_INET;
    addr.sin_addr.s_addr = inet_addr("127.0.0.1");
    addr.sin_port = htons(8585);
    bind(listenSock, (sockaddr *)&addr, sizeof(addr));
    listen(listenSock, 1);
    std::cout << "WS Server listening on 127.0.0.1:8585\n";
    while (true)
    {
        SOCKET client = accept(listenSock, nullptr, nullptr);
        if (client == INVALID_SOCKET)
            continue;
        std::string headers = read_http_header(client);
        std::string key = get_header_value(headers, "Sec-WebSocket-Key");
        if (!key.empty())
        {
            const std::string magic = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11";
            std::string accept = sha1_base64(key + magic);
            ws_send_handshake(client, accept);
            // read frames
            while (true)
            {
                std::string payload = ws_read_frame(client);
                if (payload.empty())
                    break;
                std::cout << "WS PAYLOAD: " << payload << std::endl;
                insert_raw_event(payload);
            }
        }
        closesocket(client);
    }
    closesocket(listenSock);
    WSACleanup();
}

int wmain()
{
    // init DB
    if (!init_db("cpam_cache.db"))
    {
        std::cerr << "Failed to open sqlite DB\n";
    }
    else
    {
        std::cout << "SQLite DB initialized\n";
    }

    std::thread(ws_server_thread).detach();

    HWND last = nullptr;
    wchar_t title[1024];

    while (true)
    {
        HWND fg = GetForegroundWindow();
        if (fg != last)
        {
            last = fg;
            DWORD pid = 0;
            GetWindowThreadProcessId(fg, &pid);
            if (GetWindowTextW(fg, title, _countof(title)) > 0)
            {
                std::wstring wtitle(title);
                std::wcout << L"FG: PID=" << pid << L" Title=\"" << wtitle << L"\"\n";
            }
        }
        Sleep(1000);
    }
    return 0;
}
}
