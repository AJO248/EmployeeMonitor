package main

import (
    "encoding/json"
    "fmt"
    "io"
    "log"
    "net/http"
    "time"
)

type LogEvent map[string]interface{}

func main() {
    ch := make(chan LogEvent, 1000)

    // worker
    go func() {
        for ev := range ch {
            b, _ := json.Marshal(ev)
            // For prototype, just print. Replace with DB write later.
            fmt.Printf("[worker] %s\n", string(b))
        }
    }()

    http.HandleFunc("/api/v1/logs", func(w http.ResponseWriter, r *http.Request) {
        if r.Method != http.MethodPost {
            http.Error(w, "method", http.StatusMethodNotAllowed)
            return
        }
        body, err := io.ReadAll(r.Body)
        if err != nil {
            http.Error(w, "bad body", http.StatusBadRequest)
            return
        }
        var ev LogEvent
        if err := json.Unmarshal(body, &ev); err != nil {
            http.Error(w, "invalid json", http.StatusBadRequest)
            return
        }

        select {
        case ch <- ev:
            // respond quickly to maximize throughput
            w.WriteHeader(http.StatusAccepted)
            w.Write([]byte("accepted"))
        default:
            http.Error(w, "queue full", http.StatusServiceUnavailable)
        }
    })

    srv := &http.Server{
        Addr:         ":8080",
        ReadTimeout:  5 * time.Second,
        WriteTimeout: 5 * time.Second,
    }

    log.Printf("EEAM Go ingestion server listening on :8080")
    if err := srv.ListenAndServe(); err != nil {
        log.Fatalf("server error: %v", err)
    }
}
