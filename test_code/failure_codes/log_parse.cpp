/*
 * Parses a stream of structured log entries, validates fields,
 * and builds a summary report of events by severity and source.
 *
 * Submitted by: student
 * Assignment: Lab 7 - Systems Programming
 *
 * Each log entry has the format:
 *   TIMESTAMP PID LEVEL SOURCE MESSAGE
 *
 * The parser validates each field, accumulates stats, and writes
 * a report every 1000 entries. Errors are reported to stderr.
 * If the error rate exceeds a threshold, shuts down gracefully.
 */

#include <iostream>
#include <sstream>
#include <string>
#include <vector>
#include <unordered_map>
#include <chrono>
#include <cstring>
#include <cerrno>
#include <cstdlib>
#include <cmath>

// ── Entry ─────────────────────────────────────────────────────────────────────

struct LogEntry {
    long        timestamp;
    int         pid;
    std::string level;
    std::string source;
    std::string message;
    bool        valid;

    LogEntry() : timestamp(0), pid(0), valid(false) {}
};

// ── Report accumulator ────────────────────────────────────────────────────────

struct ReportBucket {
    std::string source;
    int         info_count;
    int         warn_count;
    int         error_count;
    int         debug_count;
    long        first_seen;
    long        last_seen;

    ReportBucket()
        : info_count(0), warn_count(0),
          error_count(0), debug_count(0),
          first_seen(0), last_seen(0) {}
};

// ── Parser ────────────────────────────────────────────────────────────────────

class LogParser {
public:
    int  entries_parsed;
    int  entries_skipped;
    int  parse_errors;
    int  consecutive_errors;
    bool healthy;

    static const int MAX_CONSECUTIVE_ERRORS = 10;
    static const int MAX_MESSAGE_BYTES      = 512;
    static const int MAX_BUCKETS            = 50000;

    LogParser()
        : entries_parsed(0), entries_skipped(0),
          parse_errors(0), consecutive_errors(0),
          healthy(true) {}

    ~LogParser() {
        int freed = (int)buckets.size();
        buckets.clear();
        raw_entries.clear();

        std::cerr << "INFO: parser shutdown"
                  << " — parsed="    << entries_parsed
                  << " skipped="     << entries_skipped
                  << " errors="      << parse_errors
                  << " buckets_freed=" << freed
                  << std::endl;
        std::cerr.flush();
    }

    bool process(const std::string& raw_line, int line_num) {
        if (!healthy) return false;

        // ── Size check ────────────────────────────────────────────────────────
        if ((int)raw_line.size() > MAX_MESSAGE_BYTES) {
            std::cerr << "ERROR: line " << line_num
                      << " exceeds max size ("
                      << raw_line.size() << " > "
                      << MAX_MESSAGE_BYTES << " bytes) — skipping"
                      << std::endl;
            entries_skipped++;
            _record_error(line_num);
            return true;  // non-fatal
        }

        // ── Store raw copy ────────────────────────────────────────────────────
        char* raw = new (std::nothrow) char[raw_line.size() + 1];
        if (!raw) {
            std::cerr << "ERROR: line " << line_num
                      << " — failed to allocate raw buffer: "
                      << std::strerror(errno) << std::endl;
            _record_error(line_num);
            return healthy;
        }
        std::memcpy(raw, raw_line.c_str(), raw_line.size() + 1);
        raw_entries.push_back(raw);

        // ── Parse fields ──────────────────────────────────────────────────────
        LogEntry entry = _parse(raw_line, line_num);
        if (!entry.valid) {
            entries_skipped++;
            return healthy;
        }

        // ── Validate fields ───────────────────────────────────────────────────
        if (entry.timestamp <= 0) {
            std::cerr << "ERROR: line " << line_num
                      << " invalid timestamp ("
                      << entry.timestamp << ") — skipping" << std::endl;
            entries_skipped++;
            _record_error(line_num);
            return healthy;
        }

        if (entry.pid <= 0 || entry.pid > 65535) {
            std::cerr << "ERROR: line " << line_num
                      << " invalid PID (" << entry.pid
                      << ") — skipping" << std::endl;
            entries_skipped++;
            _record_error(line_num);
            return healthy;
        }

        if (entry.level != "INFO"  && entry.level != "WARN" &&
            entry.level != "ERROR" && entry.level != "DEBUG") {
            std::cerr << "ERROR: line " << line_num
                      << " unknown log level '"
                      << entry.level << "' — skipping" << std::endl;
            entries_skipped++;
            _record_error(line_num);
            return healthy;
        }

        if (entry.source.empty()) {
            std::cerr << "ERROR: line " << line_num
                      << " missing source field — skipping" << std::endl;
            entries_skipped++;
            _record_error(line_num);
            return healthy;
        }

        if (entry.message.empty()) {
            std::cerr << "WARN: line " << line_num
                      << " empty message field" << std::endl;
        }

        // ── Bucket limit check ────────────────────────────────────────────────
        if ((int)buckets.size() >= MAX_BUCKETS &&
            buckets.find(entry.source) == buckets.end()) {
            std::cerr << "ERROR: line " << line_num
                      << " bucket limit reached ("
                      << MAX_BUCKETS << " sources)"
                      << " — cannot add source '"
                      << entry.source << "'" << std::endl;
            _record_error(line_num);
            return healthy;
        }

        // ── Accumulate ────────────────────────────────────────────────────────
        ReportBucket& b = buckets[entry.source];
        if (b.first_seen == 0) b.first_seen = entry.timestamp;
        b.last_seen = entry.timestamp;

        if      (entry.level == "INFO")  b.info_count++;
        else if (entry.level == "WARN")  b.warn_count++;
        else if (entry.level == "ERROR") b.error_count++;
        else if (entry.level == "DEBUG") b.debug_count++;

        consecutive_errors = 0;
        entries_parsed++;
        return true;
    }

    void flush_report(double elapsed) {
        int total_warn  = 0;
        int total_error = 0;
        for (const auto& kv : buckets) {
            total_warn  += kv.second.warn_count;
            total_error += kv.second.error_count;
        }
        std::cout << "[" << elapsed << "s]"
                  << "  parsed="   << entries_parsed
                  << "  skipped="  << entries_skipped
                  << "  sources="  << buckets.size()
                  << "  warnings=" << total_warn
                  << "  errors="   << total_error
                  << "  healthy="  << (healthy ? "yes" : "NO")
                  << std::endl;
    }

    int source_count() const { return (int)buckets.size(); }

private:
    std::unordered_map<std::string, ReportBucket> buckets;
    std::vector<char*>                             raw_entries;

    LogEntry _parse(const std::string& line, int line_num) {
        LogEntry e;
        std::istringstream ss(line);
        std::string ts_str, pid_str;

        if (!(ss >> ts_str >> pid_str >> e.level >> e.source)) {
            std::cerr << "ERROR: line " << line_num
                      << " malformed — expected: "
                      << "TIMESTAMP PID LEVEL SOURCE [MESSAGE]"
                      << std::endl;
            _record_error(line_num);
            return e;
        }

        // Parse timestamp
        try {
            e.timestamp = std::stol(ts_str);
        } catch (...) {
            std::cerr << "ERROR: line " << line_num
                      << " non-numeric timestamp '"
                      << ts_str << "'" << std::endl;
            _record_error(line_num);
            return e;
        }

        // Parse PID
        try {
            e.pid = std::stoi(pid_str);
        } catch (...) {
            std::cerr << "ERROR: line " << line_num
                      << " non-numeric PID '"
                      << pid_str << "'" << std::endl;
            _record_error(line_num);
            return e;
        }

        std::getline(ss, e.message);
        if (!e.message.empty() && e.message[0] == ' ')
            e.message = e.message.substr(1);

        e.valid = true;
        return e;
    }

    void _record_error(int line_num) {
        parse_errors++;
        consecutive_errors++;
        if (consecutive_errors >= MAX_CONSECUTIVE_ERRORS) {
            std::cerr << "ERROR: " << consecutive_errors
                      << " consecutive parse errors (last at line "
                      << line_num << ") — "
                      << "input stream may be corrupt, "
                      << "marking parser unhealthy" << std::endl;
            healthy = false;
        }
    }
};

// ── Log line generator ────────────────────────────────────────────────────────

static const char* LEVELS[]   = { "INFO", "WARN", "ERROR", "DEBUG" };
static const char* SOURCES[]  = {
    "auth.service",    "db.primary",      "db.replica",
    "cache.layer",     "api.gateway",     "worker.pool",
    "scheduler",       "monitor.daemon",  "proxy.edge",
    "queue.consumer",
};
static const char* MESSAGES[] = {
    "connection established",
    "request timeout after 30s",
    "authentication failed for user",
    "cache miss ratio exceeded threshold",
    "database transaction rolled back",
    "worker thread exited unexpectedly",
    "retry limit reached",
    "handshake failed",
    "memory threshold exceeded",
    "queue depth critical",
};
static const int N_LEVELS   = 4;
static const int N_SOURCES  = 10;
static const int N_MESSAGES = 10;

// Inject realistic errors at known intervals to trigger stderr paths
std::string generate_line(int id, long base_ts) {
    srand(id * 7919 + 13);

    // Every ~50 entries: inject a malformed line (missing fields)
    if (id % 53 == 0) {
        return "MALFORMED_ENTRY_NO_FIELDS";
    }

    // Every ~80 entries: inject an invalid timestamp
    if (id % 83 == 0) {
        return "notanumber " + std::to_string(100 + rand() % 60000) + " INFO "
             + SOURCES[rand() % N_SOURCES] + " synthetic error";
    }

    // Every ~120 entries: inject an oversized line
    if (id % 127 == 0) {
        std::string fat = std::to_string(base_ts + id) + " "
                        + std::to_string(1000 + rand() % 60000)
                        + " INFO oversized.source ";
        while ((int)fat.size() < 520) fat += "x";
        return fat;
    }

    // Every ~200 entries: inject an unknown log level
    if (id % 199 == 0) {
        return std::to_string(base_ts + id) + " "
             + std::to_string(1000 + rand() % 60000)
             + " TRACE " + SOURCES[rand() % N_SOURCES]
             + " unknown level entry";
    }

    // Normal entry
    return std::to_string(base_ts + id) + " "
         + std::to_string(1000 + rand() % 60000) + " "
         + LEVELS[rand() % N_LEVELS]   + " "
         + SOURCES[rand() % N_SOURCES] + " "
         + MESSAGES[rand() % N_MESSAGES];
}

// ── Main ──────────────────────────────────────────────────────────────────────

int main() {
    std::cout << "Log parser starting" << std::endl;
    std::cout << "Processing simulated log stream..." << std::endl;
    std::cout << std::endl;

    LogParser parser;
    auto  start   = std::chrono::steady_clock::now();
    long  base_ts = 1700000000L;  // synthetic epoch base

    int line_num = 0;
    const int FLUSH_EVERY = 1000;
    const int MAX_LINES   = 500000;

    while (parser.healthy && line_num < MAX_LINES) {
        auto now     = std::chrono::steady_clock::now();
        double elapsed = std::chrono::duration<double>(now - start).count();
        if (elapsed >= 60.0) break;

        std::string line = generate_line(line_num, base_ts);
        if (!parser.process(line, line_num)) {
            if (!parser.healthy) {
                std::cerr << "ERROR: parser became unhealthy at line "
                          << line_num << " — stopping" << std::endl;
            }
            break;
        }

        line_num++;

        if (line_num % FLUSH_EVERY == 0) {
            auto now2    = std::chrono::steady_clock::now();
            double elapsed2 = std::chrono::duration<double>(now2 - start).count();
            parser.flush_report(elapsed2);
        }
    }

    // Final report
    auto end     = std::chrono::steady_clock::now();
    double total = std::chrono::duration<double>(end - start).count();
    parser.flush_report(total);

    if (!parser.healthy) {
        std::cerr << "ERROR: processing terminated early due to "
                  << parser.parse_errors << " parse errors" << std::endl;
        std::cout << "Partial results: "
                  << parser.entries_parsed << " entries across "
                  << parser.source_count() << " sources" << std::endl;
        return 1;
    }

    std::cout << "\nProcessing complete." << std::endl;
    std::cout << "Total lines    : " << line_num << std::endl;
    std::cout << "Entries parsed : " << parser.entries_parsed << std::endl;
    std::cout << "Entries skipped: " << parser.entries_skipped << std::endl;
    std::cout << "Sources found  : " << parser.source_count() << std::endl;
    return 0;
}