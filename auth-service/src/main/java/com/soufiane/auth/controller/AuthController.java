package com.soufiane.auth.controller;

import com.soufiane.auth.dto.LoginRequest;
import com.soufiane.auth.dto.LoginResponse;
import com.soufiane.auth.dto.MeResponse;
import com.soufiane.auth.dto.UpdateProfileRequest;
import com.soufiane.auth.service.AuthService;
import jakarta.validation.Valid;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
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

    public AuthController(AuthService authService) {
        this.authService = authService;
    }

    @PostMapping("/login")
    public LoginResponse login(@Valid @RequestBody LoginRequest request) {
        return authService.login(request);
    }

    // The token is stateless and short lived, so there's nothing server side
    // to invalidate yet. This exists so the frontend has one clear endpoint
    // to call when discarding it, and so a real revocation list can slot in
    // here later without the frontend needing to change.
    @PostMapping("/logout")
    @ResponseStatus(HttpStatus.NO_CONTENT)
    public void logout() {
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
