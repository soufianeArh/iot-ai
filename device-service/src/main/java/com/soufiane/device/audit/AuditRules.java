package com.soufiane.device.audit;

import java.util.Arrays;
import java.util.Map;
import java.util.Set;

// Pure functions that turn "an HTTP request just finished" into an audit row
// or into nothing. A copy of auth-service's AuditRules, not shared, keep the
// two in step.
public final class AuditRules {

    private AuditRules() {
    }

    private static final Set<String> READ_METHODS = Set.of("GET", "HEAD", "OPTIONS");
    private static final Set<String> STACK_PREFIXES = Set.of("api", "ai", "video", "auth", "internal");

    private static final Map<String, String> RESOURCE = Map.of(
            "devices", "device",
            "zones", "zone",
            "users", "user",
            "rules", "rule",
            "alerts", "alert",
            "tasks", "task",
            "camera", "camera",
            "me", "profile");

    public static boolean shouldAudit(String method, String path) {
        if (READ_METHODS.contains(method)) return false;
        if (path.startsWith("/actuator")) return false;
        if (path.endsWith("/health")) return false;
        if (path.equals("/error")) return false;   // Spring's error dispatch target
        // not real state changes: starting/stopping a stream, testing a camera
        if (path.endsWith("/stream") || path.endsWith("/probe")) return false;
        if (path.equals("/ai/chat")) return false;
        if (path.equals("/api/auth/login") || path.equals("/api/auth/logout")) return false;
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

    private static String[] segments(String path) {
        return Arrays.stream(path.split("/"))
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
