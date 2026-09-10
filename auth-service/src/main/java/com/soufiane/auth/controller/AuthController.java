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

    // Login and logout are audited here, not by the generic filter: on a
    // successful login there is still no security context to read the actor
    // from, and a failed attempt needs to record the username that was
    // tried. LOGIN / LOGOUT also read better than the filter's generic CREATE.
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

    // The token is stateless and short lived, so there's nothing server side
    // to invalidate yet. This exists so the frontend has one clear endpoint
    // to call when discarding it, and so a real revocation list can slot in
    // here later without the frontend needing to change.
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
