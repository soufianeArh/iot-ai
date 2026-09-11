package com.soufiane.auth.audit;

import com.soufiane.auth.dto.AuditReport;
import com.soufiane.auth.service.AuditService;
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

// Sits right after JwtAuthFilter in the security chain (see SecurityConfig),
// so the security context and final status are both still readable on the
// way back out. Writes straight to AuditService, this is auth-service's own
// database. Not a @Component on purpose: SecurityConfig builds it itself so
// it can't also get registered as a plain filter and double log.
public class AuditFilter extends OncePerRequestFilter {

    private static final Logger log = LoggerFactory.getLogger(AuditFilter.class);

    private final AuditService auditService;

    public AuditFilter(AuditService auditService) {
        this.auditService = auditService;
    }

    @Override
    protected void doFilterInternal(@NonNull HttpServletRequest request,
                                     @NonNull HttpServletResponse response,
                                     @NonNull FilterChain chain) throws ServletException, IOException {
        chain.doFilter(request, response);
        try {
            maybeRecord(request, response);
        } catch (Exception e) {
            // Auditing must never break the request it is auditing.
            log.debug("audit skipped for {} {}: {}", request.getMethod(), request.getRequestURI(), e.toString());
        }
    }

    private void maybeRecord(HttpServletRequest request, HttpServletResponse response) {
        String method = request.getMethod();
        String path = request.getRequestURI();
        if (!AuditRules.shouldAudit(method, path)) return;

        Authentication auth = SecurityContextHolder.getContext().getAuthentication();
        String actor = auth != null ? auth.getName() : null;
        String role = roleOf(auth);
        // A service token is the stack talking to itself, not a person.
        if ("SERVICE".equals(role)) return;

        int status = response.getStatus();
        auditService.record(new AuditReport(
                actor, role, "auth-service", method,
                AuditRules.action(method, path), AuditRules.resource(path), AuditRules.resourceId(path),
                path, status, AuditRules.outcome(status), clientIp(request)));
    }

    // public so AuthController can reuse them for the explicit login / logout rows.
    public static String roleOf(Authentication auth) {
        if (auth == null) return null;
        return auth.getAuthorities().stream().findFirst()
                .map(a -> a.getAuthority().replaceFirst("^ROLE_", ""))
                .orElse(null);
    }

    public static String clientIp(HttpServletRequest request) {
        String forwarded = request.getHeader("X-Forwarded-For");
        if (forwarded != null && !forwarded.isBlank()) {
            return forwarded.split(",")[0].trim();
        }
        return request.getRemoteAddr();
    }
}
