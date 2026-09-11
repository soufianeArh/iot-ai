package com.soufiane.device.audit;

import jakarta.servlet.FilterChain;
import jakarta.servlet.ServletException;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.lang.NonNull;
import org.springframework.security.core.Authentication;
import org.springframework.security.core.context.SecurityContextHolder;
import org.springframework.web.filter.OncePerRequestFilter;

import java.io.IOException;

// Sits right after JwtAuthFilter in the security chain (see SecurityConfig)
// so the security context and final status are both still readable on the
// way back out. Ships each row to auth-service via AuditReporter.
public class AuditFilter extends OncePerRequestFilter {

    private static final Logger log = LoggerFactory.getLogger(AuditFilter.class);

    private final AuditReporter reporter;

    public AuditFilter(AuditReporter reporter) {
        this.reporter = reporter;
    }

    @Override
    protected void doFilterInternal(@NonNull HttpServletRequest request,
                                     @NonNull HttpServletResponse response,
                                     @NonNull FilterChain chain) throws ServletException, IOException {
        chain.doFilter(request, response);
        try {
            maybeReport(request, response);
        } catch (Exception e) {
            log.debug("audit skipped for {} {}: {}", request.getMethod(), request.getRequestURI(), e.toString());
        }
    }

    private void maybeReport(HttpServletRequest request, HttpServletResponse response) {
        String method = request.getMethod();
        String path = request.getRequestURI();
        if (!AuditRules.shouldAudit(method, path)) return;

        Authentication auth = SecurityContextHolder.getContext().getAuthentication();
        String role = roleOf(auth);
        // A SERVICE token here is ai-service calling device-service, not a person.
        if ("SERVICE".equals(role)) return;

        String actor = auth != null ? auth.getName() : null;
        int status = response.getStatus();
        reporter.send(new AuditReport(
                actor, role, "device-service", method,
                AuditRules.action(method, path), AuditRules.resource(path), AuditRules.resourceId(path),
                path, status, AuditRules.outcome(status), clientIp(request)));
    }

    private static String roleOf(Authentication auth) {
        if (auth == null) return null;
        return auth.getAuthorities().stream().findFirst()
                .map(a -> a.getAuthority().replaceFirst("^ROLE_", ""))
                .orElse(null);
    }

    private static String clientIp(HttpServletRequest request) {
        String forwarded = request.getHeader("X-Forwarded-For");
        if (forwarded != null && !forwarded.isBlank()) {
            return forwarded.split(",")[0].trim();
        }
        return request.getRemoteAddr();
    }
}
