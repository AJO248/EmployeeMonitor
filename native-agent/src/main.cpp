#define NOMINMAX

#include <winsock2.h>
#include <ws2tcpip.h>
#include <windows.h>
#include <winhttp.h>

#include <sqlite3.h>

#include <algorithm>
#include <chrono>
#include <cstdint>
#include <cstdlib>
#include <iostream>
#include <mutex>
#include <sstream>
#include <string>
#include <thread>
#include <vector>

namespace
{
constexpr char kCachePath[] = "em_cache.db";
constexpr wchar_t kDefaultBackendUrl[] = L"http://127.0.0.1:8000/api/v1/logs";
constexpr wchar_t kDefaultIngestToken[] = L"development-ingest-token";
constexpr size_t kBatchSize = 100;
constexpr DWORD kIdleThresholdMilliseconds = 5 * 60 * 1000;
constexpr auto kHeartbeatInterval = std::chrono::seconds(60);

sqlite3 *database = nullptr;
std::mutex database_mutex;

struct CachedEvent
{
    sqlite3_int64 id;
    std::string raw;
};

std::string base64_encode(const unsigned char *data, size_t length)
{
    static const char *table = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/";
    std::string output;
    uint32_t value = 0;
    int bits = -6;
    for (size_t index = 0; index < length; ++index)
    {
        value = (value << 8) + data[index];
        bits += 8;
        while (bits >= 0)
        {
            output.push_back(table[(value >> bits) & 0x3f]);
            bits -= 6;
        }
    }
    if (bits > -6)
        output.push_back(table[((value << 8) >> (bits + 8)) & 0x3f]);
    while (output.size() % 4)
        output.push_back('=');
    return output;
}

std::vector<unsigned char> base64_decode(const std::string &value)
{
    std::vector<unsigned char> output;
    uint32_t accumulator = 0;
    int bits = -8;
    for (unsigned char character : value)
    {
        int decoded = -1;
        if (character >= 'A' && character <= 'Z')
            decoded = character - 'A';
        else if (character >= 'a' && character <= 'z')
            decoded = character - 'a' + 26;
        else if (character >= '0' && character <= '9')
            decoded = character - '0' + 52;
        else if (character == '+')
            decoded = 62;
        else if (character == '/')
            decoded = 63;
        else if (character == '=')
            break;
        if (decoded < 0)
            continue;

        accumulator = (accumulator << 6) + decoded;
        bits += 6;
        if (bits >= 0)
        {
            output.push_back(static_cast<unsigned char>((accumulator >> bits) & 0xff));
            bits -= 8;
        }
    }
    return output;
}

std::string protect_cache_value(const std::string &raw)
{
    DATA_BLOB input{};
    input.pbData = reinterpret_cast<BYTE *>(const_cast<char *>(raw.data()));
    input.cbData = static_cast<DWORD>(raw.size());
    DATA_BLOB encrypted{};
    if (!CryptProtectData(&input, L"EM cache event", nullptr, nullptr, nullptr,
                          CRYPTPROTECT_UI_FORBIDDEN | CRYPTPROTECT_LOCAL_MACHINE, &encrypted))
        return {};

    const std::string protected_value =
        "dpapi:" + base64_encode(encrypted.pbData, encrypted.cbData);
    LocalFree(encrypted.pbData);
    return protected_value;
}

std::string unprotect_cache_value(const std::string &stored)
{
    if (stored.rfind("dpapi:", 0) != 0)
        return stored;

    std::vector<unsigned char> encrypted = base64_decode(stored.substr(6));
    if (encrypted.empty())
        return {};
    DATA_BLOB input{};
    input.pbData = encrypted.data();
    input.cbData = static_cast<DWORD>(encrypted.size());
    DATA_BLOB decrypted{};
    if (!CryptUnprotectData(&input, nullptr, nullptr, nullptr, nullptr,
                            CRYPTPROTECT_UI_FORBIDDEN, &decrypted))
        return {};

    const std::string raw(reinterpret_cast<char *>(decrypted.pbData), decrypted.cbData);
    LocalFree(decrypted.pbData);
    return raw;
}

std::string sha1_base64(const std::string &input)
{
    HCRYPTPROV provider = 0;
    HCRYPTHASH hash = 0;
    std::string result;
    if (!CryptAcquireContextW(&provider, nullptr, nullptr, PROV_RSA_FULL, CRYPT_VERIFYCONTEXT))
        return result;
    if (!CryptCreateHash(provider, CALG_SHA1, 0, 0, &hash))
    {
        CryptReleaseContext(provider, 0);
        return result;
    }

    CryptHashData(hash, reinterpret_cast<const BYTE *>(input.data()), static_cast<DWORD>(input.size()), 0);
    BYTE digest[20];
    DWORD digest_length = sizeof(digest);
    if (CryptGetHashParam(hash, HP_HASHVAL, digest, &digest_length, 0))
        result = base64_encode(digest, digest_length);

    CryptDestroyHash(hash);
    CryptReleaseContext(provider, 0);
    return result;
}

std::string to_utf8(const std::wstring &value)
{
    if (value.empty())
        return {};
    const int length = WideCharToMultiByte(CP_UTF8, 0, value.c_str(), static_cast<int>(value.size()), nullptr, 0, nullptr, nullptr);
    std::string output(length, '\0');
    WideCharToMultiByte(CP_UTF8, 0, value.c_str(), static_cast<int>(value.size()), output.data(), length, nullptr, nullptr);
    return output;
}

std::string json_escape(const std::string &value)
{
    std::ostringstream output;
    for (unsigned char character : value)
    {
        switch (character)
        {
        case '"':
            output << "\\\"";
            break;
        case '\\':
            output << "\\\\";
            break;
        case '\b':
            output << "\\b";
            break;
        case '\f':
            output << "\\f";
            break;
        case '\n':
            output << "\\n";
            break;
        case '\r':
            output << "\\r";
            break;
        case '\t':
            output << "\\t";
            break;
        default:
            if (character < 0x20)
            {
                const char hex[] = "0123456789abcdef";
                output << "\\u00" << hex[character >> 4] << hex[character & 0x0f];
            }
            else
            {
                output << character;
            }
        }
    }
    return output.str();
}

sqlite3_int64 now_seconds()
{
    return static_cast<sqlite3_int64>(std::chrono::system_clock::to_time_t(std::chrono::system_clock::now()));
}

long long now_milliseconds()
{
    return std::chrono::duration_cast<std::chrono::milliseconds>(
               std::chrono::system_clock::now().time_since_epoch())
        .count();
}

void execute_schema_statement(const char *sql)
{
    char *error = nullptr;
    sqlite3_exec(database, sql, nullptr, nullptr, &error);
    if (error)
        sqlite3_free(error);
}

bool init_database(const char *path)
{
    std::lock_guard<std::mutex> lock(database_mutex);
    if (sqlite3_open_v2(path, &database, SQLITE_OPEN_READWRITE | SQLITE_OPEN_CREATE | SQLITE_OPEN_FULLMUTEX, nullptr) != SQLITE_OK)
        return false;

    execute_schema_statement(
        "CREATE TABLE IF NOT EXISTS events ("
        "id INTEGER PRIMARY KEY, raw TEXT NOT NULL, received_at INTEGER NOT NULL, "
        "delivered_at INTEGER, attempts INTEGER NOT NULL DEFAULT 0);");
    execute_schema_statement("CREATE INDEX IF NOT EXISTS idx_events_pending ON events(delivered_at, id);");
    return true;
}

void insert_raw_event(const std::string &raw)
{
    std::lock_guard<std::mutex> lock(database_mutex);
    if (!database)
        return;

    const std::string protected_value = protect_cache_value(raw);
    if (protected_value.empty())
    {
        std::cerr << "Could not protect cache event with DPAPI\n";
        return;
    }

    sqlite3_stmt *statement = nullptr;
    const char *sql = "INSERT INTO events (raw, received_at) VALUES (?, ?);";
    if (sqlite3_prepare_v2(database, sql, -1, &statement, nullptr) != SQLITE_OK)
        return;
    sqlite3_bind_text(statement, 1, protected_value.c_str(), static_cast<int>(protected_value.size()), SQLITE_TRANSIENT);
    sqlite3_bind_int64(statement, 2, now_seconds());
    sqlite3_step(statement);
    sqlite3_finalize(statement);
}

std::vector<CachedEvent> read_pending_events()
{
    std::lock_guard<std::mutex> lock(database_mutex);
    std::vector<CachedEvent> events;
    sqlite3_stmt *statement = nullptr;
    const char *sql = "SELECT id, raw FROM events WHERE delivered_at IS NULL ORDER BY id LIMIT ?;";
    if (sqlite3_prepare_v2(database, sql, -1, &statement, nullptr) != SQLITE_OK)
        return events;
    sqlite3_bind_int(statement, 1, static_cast<int>(kBatchSize));

    while (sqlite3_step(statement) == SQLITE_ROW)
    {
        const auto *raw = reinterpret_cast<const char *>(sqlite3_column_text(statement, 1));
        if (raw)
        {
            const std::string unprotected = unprotect_cache_value(raw);
            if (!unprotected.empty())
                events.push_back({sqlite3_column_int64(statement, 0), unprotected});
        }
    }
    sqlite3_finalize(statement);
    return events;
}

void update_delivery_state(const std::vector<CachedEvent> &events, bool delivered)
{
    std::lock_guard<std::mutex> lock(database_mutex);
    sqlite3_exec(database, "BEGIN;", nullptr, nullptr, nullptr);
    sqlite3_stmt *statement = nullptr;
    const char *sql = delivered
                          ? "UPDATE events SET delivered_at = ?, attempts = attempts + 1 WHERE id = ?;"
                          : "UPDATE events SET attempts = attempts + 1 WHERE id = ?;";
    if (sqlite3_prepare_v2(database, sql, -1, &statement, nullptr) == SQLITE_OK)
    {
        for (const CachedEvent &event : events)
        {
            if (delivered)
            {
                sqlite3_bind_int64(statement, 1, now_seconds());
                sqlite3_bind_int64(statement, 2, event.id);
            }
            else
            {
                sqlite3_bind_int64(statement, 1, event.id);
            }
            sqlite3_step(statement);
            sqlite3_reset(statement);
            sqlite3_clear_bindings(statement);
        }
        sqlite3_finalize(statement);
    }
    sqlite3_exec(database, "COMMIT;", nullptr, nullptr, nullptr);
}

std::string device_id()
{
    wchar_t name[MAX_COMPUTERNAME_LENGTH + 1];
    DWORD length = _countof(name);
    if (!GetComputerNameW(name, &length))
        return "unknown-windows-device";
    return to_utf8(std::wstring(name, length));
}

std::wstring backend_url()
{
    const wchar_t *configured = _wgetenv(L"EM_BACKEND_URL");
    return configured && *configured ? configured : kDefaultBackendUrl;
}

std::wstring ingest_token()
{
    const wchar_t *configured = _wgetenv(L"EM_INGEST_TOKEN");
    return configured && *configured ? configured : kDefaultIngestToken;
}

std::string make_batch(const std::vector<CachedEvent> &events)
{
    std::ostringstream body;
    body << "{\"device_id\":\"" << json_escape(device_id()) << "\",\"entries\":[";
    for (size_t index = 0; index < events.size(); ++index)
    {
        if (index)
            body << ',';
        body << events[index].raw;
    }
    body << "]}";
    return body.str();
}

bool post_json(const std::wstring &url, const std::string &body)
{
    URL_COMPONENTS components{};
    components.dwStructSize = sizeof(components);
    components.dwSchemeLength = static_cast<DWORD>(-1);
    components.dwHostNameLength = static_cast<DWORD>(-1);
    components.dwUrlPathLength = static_cast<DWORD>(-1);
    components.dwExtraInfoLength = static_cast<DWORD>(-1);
    if (!WinHttpCrackUrl(url.c_str(), 0, 0, &components))
        return false;

    const std::wstring host(components.lpszHostName, components.dwHostNameLength);
    std::wstring path(components.lpszUrlPath, components.dwUrlPathLength);
    if (components.dwExtraInfoLength)
        path.append(components.lpszExtraInfo, components.dwExtraInfoLength);
    const bool secure = components.nScheme == INTERNET_SCHEME_HTTPS;

    HINTERNET session = WinHttpOpen(L"EM Native Agent/0.2", WINHTTP_ACCESS_TYPE_AUTOMATIC_PROXY, nullptr, nullptr, 0);
    if (!session)
        return false;
    WinHttpSetTimeouts(session, 5000, 5000, 10000, 10000);
    HINTERNET connection = WinHttpConnect(session, host.c_str(), components.nPort, 0);
    HINTERNET request = connection ? WinHttpOpenRequest(
                                         connection, L"POST", path.c_str(), nullptr, WINHTTP_NO_REFERER,
                                         WINHTTP_DEFAULT_ACCEPT_TYPES, secure ? WINHTTP_FLAG_SECURE : 0)
                                   : nullptr;

    bool success = false;
    if (request)
    {
        const std::wstring headers = L"Content-Type: application/json\r\nAuthorization: Bearer " +
                                     ingest_token() + L"\r\n";
        if (WinHttpSendRequest(request, headers.c_str(), static_cast<DWORD>(-1L),
                               const_cast<char *>(body.data()), static_cast<DWORD>(body.size()),
                               static_cast<DWORD>(body.size()), 0) &&
            WinHttpReceiveResponse(request, nullptr))
        {
            DWORD status = 0;
            DWORD size = sizeof(status);
            if (WinHttpQueryHeaders(request, WINHTTP_QUERY_STATUS_CODE | WINHTTP_QUERY_FLAG_NUMBER,
                                    WINHTTP_HEADER_NAME_BY_INDEX, &status, &size, WINHTTP_NO_HEADER_INDEX))
                success = status >= 200 && status < 300;
        }
    }

    if (request)
        WinHttpCloseHandle(request);
    if (connection)
        WinHttpCloseHandle(connection);
    WinHttpCloseHandle(session);
    return success;
}

void flush_worker()
{
    unsigned int retry_seconds = 5;
    while (true)
    {
        const std::vector<CachedEvent> events = read_pending_events();
        if (events.empty())
        {
            retry_seconds = 5;
            std::this_thread::sleep_for(std::chrono::seconds(5));
            continue;
        }

        const bool delivered = post_json(backend_url(), make_batch(events));
        update_delivery_state(events, delivered);
        if (delivered)
        {
            std::cout << "Uploaded " << events.size() << " cached event(s)\n";
            retry_seconds = 5;
        }
        else
        {
            std::cerr << "Upload failed; retrying in " << retry_seconds << " seconds\n";
            std::this_thread::sleep_for(std::chrono::seconds(retry_seconds));
            retry_seconds = std::min(retry_seconds * 2, 300u);
        }
    }
}

bool receive_exact(SOCKET socket, char *buffer, size_t length)
{
    size_t received = 0;
    while (received < length)
    {
        const int count = recv(socket, buffer + received, static_cast<int>(length - received), 0);
        if (count <= 0)
            return false;
        received += count;
    }
    return true;
}

std::string read_http_header(SOCKET socket)
{
    std::string header;
    char buffer[1024];
    int count = 0;
    while ((count = recv(socket, buffer, sizeof(buffer), 0)) > 0)
    {
        header.append(buffer, count);
        if (header.find("\r\n\r\n") != std::string::npos)
            break;
    }
    return header;
}

std::string get_header_value(const std::string &headers, const std::string &key)
{
    const std::string prefix = key + ": ";
    const size_t start = headers.find(prefix);
    if (start == std::string::npos)
        return {};
    const size_t value_start = start + prefix.size();
    const size_t end = headers.find('\r', value_start);
    return headers.substr(value_start, end - value_start);
}

void send_websocket_handshake(SOCKET client, const std::string &accept)
{
    const std::string response = "HTTP/1.1 101 Switching Protocols\r\n"
                                 "Upgrade: websocket\r\n"
                                 "Connection: Upgrade\r\n"
                                 "Sec-WebSocket-Accept: " +
                                 accept + "\r\n\r\n";
    send(client, response.c_str(), static_cast<int>(response.size()), 0);
}

std::string read_websocket_frame(SOCKET client)
{
    unsigned char header[2];
    if (!receive_exact(client, reinterpret_cast<char *>(header), sizeof(header)))
        return {};
    if ((header[0] & 0x0f) == 0x08)
        return {};

    uint64_t payload_length = header[1] & 0x7f;
    if (payload_length == 126)
    {
        unsigned char extended[2];
        if (!receive_exact(client, reinterpret_cast<char *>(extended), sizeof(extended)))
            return {};
        payload_length = (extended[0] << 8) | extended[1];
    }
    else if (payload_length == 127)
    {
        unsigned char extended[8];
        if (!receive_exact(client, reinterpret_cast<char *>(extended), sizeof(extended)))
            return {};
        payload_length = 0;
        for (unsigned char byte : extended)
            payload_length = (payload_length << 8) | byte;
    }
    if (payload_length > 1024 * 1024)
        return {};

    unsigned char mask[4]{};
    const bool masked = (header[1] & 0x80) != 0;
    if (masked && !receive_exact(client, reinterpret_cast<char *>(mask), sizeof(mask)))
        return {};

    std::string payload(payload_length, '\0');
    if (!receive_exact(client, payload.data(), payload.size()))
        return {};
    if (masked)
    {
        for (size_t index = 0; index < payload.size(); ++index)
            payload[index] ^= mask[index % 4];
    }
    return payload;
}

void websocket_server()
{
    WSADATA data;
    if (WSAStartup(MAKEWORD(2, 2), &data) != 0)
        return;

    SOCKET listener = socket(AF_INET, SOCK_STREAM, IPPROTO_TCP);
    sockaddr_in address{};
    address.sin_family = AF_INET;
    address.sin_addr.s_addr = inet_addr("127.0.0.1");
    address.sin_port = htons(8585);
    if (listener == INVALID_SOCKET ||
        bind(listener, reinterpret_cast<sockaddr *>(&address), sizeof(address)) == SOCKET_ERROR ||
        listen(listener, SOMAXCONN) == SOCKET_ERROR)
    {
        std::cerr << "Could not start WebSocket server on 127.0.0.1:8585\n";
        if (listener != INVALID_SOCKET)
            closesocket(listener);
        WSACleanup();
        return;
    }

    std::cout << "WebSocket server listening on 127.0.0.1:8585\n";
    while (true)
    {
        SOCKET client = accept(listener, nullptr, nullptr);
        if (client == INVALID_SOCKET)
            continue;
        std::thread([client]() {
            const std::string headers = read_http_header(client);
            const std::string key = get_header_value(headers, "Sec-WebSocket-Key");
            if (!key.empty())
            {
                send_websocket_handshake(client, sha1_base64(key + "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"));
                while (true)
                {
                    const std::string payload = read_websocket_frame(client);
                    if (payload.empty())
                        break;
                    insert_raw_event(payload);
                }
            }
            closesocket(client);
        }).detach();
    }
}

std::wstring process_name(DWORD process_id)
{
    HANDLE process = OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, FALSE, process_id);
    if (!process)
        return {};
    wchar_t path[32768];
    DWORD length = _countof(path);
    std::wstring result;
    if (QueryFullProcessImageNameW(process, 0, path, &length))
    {
        result.assign(path, length);
        const size_t separator = result.find_last_of(L"\\/");
        if (separator != std::wstring::npos)
            result.erase(0, separator + 1);
    }
    CloseHandle(process);
    return result;
}

void capture_foreground_window(HWND window)
{
    if (!window)
        return;
    DWORD process_id = 0;
    GetWindowThreadProcessId(window, &process_id);
    wchar_t title_buffer[1024]{};
    GetWindowTextW(window, title_buffer, _countof(title_buffer));

    const std::string title = to_utf8(title_buffer);
    const std::string app_name = to_utf8(process_name(process_id));
    std::ostringstream event;
    event << "{\"type\":\"foreground_changed\",\"app_name\":\"" << json_escape(app_name)
          << "\",\"title\":\"" << json_escape(title) << "\",\"timestamp\":" << now_milliseconds() << '}';
    insert_raw_event(event.str());
    std::wcout << L"Foreground: " << process_name(process_id) << L" - " << title_buffer << L'\n';
}

bool is_idle()
{
    LASTINPUTINFO input{};
    input.cbSize = sizeof(input);
    if (!GetLastInputInfo(&input))
        return false;
    return GetTickCount() - input.dwTime >= kIdleThresholdMilliseconds;
}

void capture_idle_transition(bool idle)
{
    std::ostringstream event;
    event << "{\"type\":\"" << (idle ? "idle_started" : "idle_ended")
          << "\",\"timestamp\":" << now_milliseconds() << '}';
    insert_raw_event(event.str());
    std::cout << (idle ? "Device became idle\n" : "Device became active\n");
}

void capture_heartbeat(bool idle)
{
    std::ostringstream event;
    event << "{\"type\":\"" << (idle ? "idle_heartbeat" : "active_heartbeat")
          << "\",\"timestamp\":" << now_milliseconds() << '}';
    insert_raw_event(event.str());
}
} // namespace

int wmain()
{
    if (!init_database(kCachePath))
    {
        std::cerr << "Failed to open SQLite cache\n";
        return 1;
    }

    std::cout << "SQLite cache initialized; backend URL: " << to_utf8(backend_url()) << '\n';
    std::thread(websocket_server).detach();
    std::thread(flush_worker).detach();

    HWND previous = nullptr;
    bool previous_idle = is_idle();
    auto last_heartbeat = std::chrono::steady_clock::now() - kHeartbeatInterval;
    while (true)
    {
        const bool idle = is_idle();
        if (idle != previous_idle)
        {
            previous_idle = idle;
            capture_idle_transition(idle);
        }
        if (std::chrono::steady_clock::now() - last_heartbeat >= kHeartbeatInterval)
        {
            capture_heartbeat(idle);
            last_heartbeat = std::chrono::steady_clock::now();
        }

        HWND foreground = GetForegroundWindow();
        if (foreground != previous)
        {
            previous = foreground;
            capture_foreground_window(foreground);
        }
        Sleep(1000);
    }
}
