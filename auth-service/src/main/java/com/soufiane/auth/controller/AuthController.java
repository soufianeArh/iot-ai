package com.soufiane.auth.controller;

import com.soufiane.auth.audit.AuditFilter;
import com.soufiane.auth.dto.LoginRequest;
import com.soufiane.auth.dto.LoginResponse;
import com.soufiane.auth.dto.MeResponse;
import com.soufiane.auth.dto.UpdateProfileRequest;
import com.soufiane.auth.service.AuditService;
import com.soufiane.auth.service.AuthService;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.validation.Valid;
import org.springframework.http.HttpStatus;
import org.springframework.security.core.Authentication;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.PutMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.ResponseStatus;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping("/api/auth")
public class AuthController {

    private final AuthService authService;
    private final AuditService auditService;

    public AuthController(AuthService authService, AuditService auditService) {
        this.authService = authService;
        this.auditService = auditService;
    }

    // Audited here, not by the generic filter: there's no security context
    // yet on a successful login, and a failed attempt still needs the
    // username that was tried.
    @PostMapping("/login")
    public LoginResponse login(@Valid @RequestBody LoginRequest request, HttpServletRequest http) {
        String ip = AuditFilter.clientIp(http);
        try {
            LoginResponse res = authService.login(request);
            auditService.record(res.username(), res.role(), "LOGIN", "session", null,
                    "/api/auth/login", 200, "SUCCESS", ip);
            return res;
        } catch (RuntimeException e) {
            auditService.record(request.username(), null, "LOGIN", "session", null,
                    "/api/auth/login", 401, "REJECTED", ip);
            throw e;
        }
    }

    // Nothing to invalidate server side yet, the token is stateless. Gives
    // the frontend one clear endpoint to call when it discards it.
    @PostMapping("/logout")
    @ResponseStatus(HttpStatus.NO_CONTENT)
    public void logout(Authentication authentication, HttpServletRequest http) {
        String actor = authentication != null ? authentication.getName() : null;
        auditService.record(actor, AuditFilter.roleOf(authentication), "LOGOUT", "session", null,
                "/api/auth/logout", 204, "SUCCESS", AuditFilter.clientIp(http));
    }

    @GetMapping("/me")
    public MeResponse me(Authentication authentication) {
        return authService.me(authentication.getName());
    }

    @PutMapping("/me")
    public MeResponse updateMe(Authentication authentication, @RequestBody UpdateProfileRequest request) {
        return authService.updateProfile(authentication.getName(), request);
    }
}
