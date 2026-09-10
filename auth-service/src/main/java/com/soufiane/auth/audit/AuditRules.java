package com.soufiane.auth.audit;

import java.util.List;
import java.util.Map;
import java.util.Set;

// The generic rules that turn "an HTTP request just finished" into an audit
// row, or into nothing. Kept as pure functions so the servlet filter that
// uses them stays tiny, and so the same logic is easy to mirror in the
// other services (device-service has its own copy, the Python services a
// port of it).
//
// Reads are never audited. A handful of writes are skipped because they are
// not meaningful actions (a health check, starting a stream, the chat
// endpoint). Login and logout are recorded explicitly by AuthService, not
// here, because at that point there is no security context to read the
// actor from.
public final class AuditRules {

    private AuditRules() {
    }

    private static final Set<String> READ_METHODS = Set.of("GET", "HEAD", "OPTIONS");

    private static final Set<String> SKIP_EXACT = Set.of(
            "/api/auth/login", "/api/auth/logout");

    private static final List<String> SKIP_PREFIX = List.of(
            "/actuator", "/internal");

    // Path segment -> resource code shown in the log. Anything not listed
    // falls back to the raw first meaningful segment.
    private static final Map<String, String> RESOURCE = Map.of(
            "devices", "device",
            "zones", "zone",
            "users", "user",
            "rules", "rule",
            "alerts", "alert",
            "tasks", "task",
            "camera", "camera",
            "me", "profile");

    private static final Set<String> STACK_PREFIXES = Set.of("api", "ai", "video", "auth", "internal");

    public static boolean shouldAudit(String method, String path) {
        if (READ_METHODS.contains(method)) return false;
        if (SKIP_EXACT.contains(path)) return false;
        for (String p : SKIP_PREFIX) {
            if (path.startsWith(p)) return false;
        }
        if (path.endsWith("/health")) return false;
        if (path.equals("/error")) return false;   // Spring's error dispatch target
        // not real state changes: starting/stopping a stream, testing a camera
        if (path.endsWith("/stream") || path.endsWith("/probe")) return false;
        if (path.equals("/ai/chat")) return false;
        return method.equals("POST") || method.equals("PUT")
                || method.equals("PATCH") || method.equals("DELETE");
    }

    public static String action(String method, String path) {
        if (path.endsWith("/ack")) return "ACK";
        return switch (method) {
            case "POST" -> "CREATE";
            case "PUT", "PATCH" -> "UPDATE";
            case "DELETE" -> "DELETE";
            default -> method;
        };
    }

    public static String outcome(int status) {
        if (status >= 200 && status < 300) return "SUCCESS";
        if (status == 401 || status == 403) return "DENIED";
        if (status >= 400 && status < 500) return "REJECTED";
        if (status >= 500) return "ERROR";
        return "SUCCESS";
    }

    // The meaningful path segments, stack prefix stripped. "/api/auth/users/4"
    // -> ["users", "4"], "/api/devices" -> ["devices"].
    private static String[] segments(String path) {
        return java.util.Arrays.stream(path.split("/"))
                .filter(s -> !s.isBlank())
                .filter(s -> !STACK_PREFIXES.contains(s))
                .toArray(String[]::new);
    }

    public static String resource(String path) {
        String[] seg = segments(path);
        if (seg.length == 0) return null;
        return RESOURCE.getOrDefault(seg[0], seg[0]);
    }

    public static String resourceId(String path) {
        String[] seg = segments(path);
        if (seg.length >= 2 && seg[1].chars().allMatch(Character::isDigit)) return seg[1];
        return null;
    }
}
