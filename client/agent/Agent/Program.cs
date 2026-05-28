using System;
using System.Net;
using System.Net.WebSockets;
using System.Runtime.InteropServices;
using System.Text;
using System.Threading;
using System.Threading.Tasks;

class Program
{
    [DllImport("user32.dll")]
    private static extern IntPtr GetForegroundWindow();

    [DllImport("user32.dll", CharSet = CharSet.Unicode)]
    private static extern int GetWindowText(IntPtr hWnd, StringBuilder text, int count);

    static async Task Main(string[] args)
    {
        Console.WriteLine("EEAM C# Agent Prototype starting...");

        var cts = new CancellationTokenSource();

        // Start WebSocket server on background
        _ = RunWebSocketServerAsync(cts.Token);

        // Poll foreground window every 5 seconds
        while (!cts.IsCancellationRequested)
        {
            try
            {
                var hWnd = GetForegroundWindow();
                var sb = new StringBuilder(1024);
                GetWindowText(hWnd, sb, sb.Capacity);
                var title = sb.ToString();
                Console.WriteLine($"Foreground window title: {title}");
            }
            catch (Exception ex)
            {
                Console.WriteLine($"Poll error: {ex.Message}");
            }
            await Task.Delay(TimeSpan.FromSeconds(5), cts.Token);
        }
    }

    static async Task RunWebSocketServerAsync(CancellationToken token)
    {
        var listener = new HttpListener();
        listener.Prefixes.Add("http://127.0.0.1:8765/ws/");
        listener.Start();
        Console.WriteLine("WebSocket server listening on ws://127.0.0.1:8765/ws/");

        while (!token.IsCancellationRequested)
        {
            HttpListenerContext context = null;
            try
            {
                context = await listener.GetContextAsync();
            }
            catch (HttpListenerException) { break; }
            catch (Exception ex)
            {
                Console.WriteLine($"Listener error: {ex.Message}");
                continue;
            }

            if (context.Request.IsWebSocketRequest)
            {
                _ = HandleWebSocketContextAsync(context);
            }
            else
            {
                context.Response.StatusCode = 400;
                context.Response.Close();
            }
        }

        listener.Close();
    }

    static async Task HandleWebSocketContextAsync(HttpListenerContext context)
    {
        WebSocketContext wsContext = null;
        try
        {
            wsContext = await context.AcceptWebSocketAsync(subProtocol: null);
        }
        catch (Exception ex)
        {
            context.Response.StatusCode = 500;
            context.Response.Close();
            Console.WriteLine($"WebSocket accept error: {ex.Message}");
            return;
        }

        var socket = wsContext.WebSocket;
        var buffer = new byte[4096];

        Console.WriteLine("WebSocket client connected");

        try
        {
            while (socket.State == WebSocketState.Open)
            {
                var result = await socket.ReceiveAsync(new ArraySegment<byte>(buffer), CancellationToken.None);
                if (result.MessageType == WebSocketMessageType.Close)
                {
                    await socket.CloseAsync(WebSocketCloseStatus.NormalClosure, "Closing", CancellationToken.None);
                    break;
                }

                var message = Encoding.UTF8.GetString(buffer, 0, result.Count);
                Console.WriteLine($"[WS] {message}");
            }
        }
        catch (Exception ex)
        {
            Console.WriteLine($"WebSocket error: {ex.Message}");
        }
        finally
        {
            socket.Dispose();
            Console.WriteLine("WebSocket client disconnected");
        }
    }
}
