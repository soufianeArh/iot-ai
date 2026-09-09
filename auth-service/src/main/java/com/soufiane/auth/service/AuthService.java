package com.soufiane.auth.service;

import com.soufiane.auth.dto.LoginRequest;
import com.soufiane.auth.dto.LoginResponse;
import com.soufiane.auth.dto.MeResponse;
import com.soufiane.auth.dto.UpdateProfileRequest;
import com.soufiane.auth.entity.User;
import com.soufiane.auth.exception.InvalidCredentialsException;
import com.soufiane.auth.repository.UserRepository;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@Service
public class AuthService {

    private final UserRepository userRepository;
    private final PasswordEncoder passwordEncoder;
    private final JwtService jwtService;

    public AuthService(UserRepository userRepository, PasswordEncoder passwordEncoder, JwtService jwtService) {
        this.userRepository = userRepository;
        this.passwordEncoder = passwordEncoder;
        this.jwtService = jwtService;
    }

    public LoginResponse login(LoginRequest request) {
        User user = userRepository.findByUsername(request.username())
                .orElseThrow(InvalidCredentialsException::new);
        if (!passwordEncoder.matches(request.password(), user.getPasswordHash())) {
            throw new InvalidCredentialsException();
        }
        String token = jwtService.issue(user);
        return new LoginResponse(token, user.getUsername(), user.getDisplayName(), user.getRole());
    }

    public MeResponse me(String username) {
        User user = userRepository.findByUsername(username)
                .orElseThrow(InvalidCredentialsException::new);
        return new MeResponse(user.getId(), user.getUsername(), user.getDisplayName(), user.getRole(), user.getCreatedAt());
    }

    @Transactional
    public MeResponse updateProfile(String username, UpdateProfileRequest request) {
        User user = userRepository.findByUsername(username)
                .orElseThrow(InvalidCredentialsException::new);

        if (request.displayName() != null && !request.displayName().isBlank()) {
            user.setDisplayName(request.displayName());
        }

        if (request.newPassword() != null && !request.newPassword().isBlank()) {
            if (request.currentPassword() == null
                    || !passwordEncoder.matches(request.currentPassword(), user.getPasswordHash())) {
                throw new InvalidCredentialsException();
            }
            user.setPasswordHash(passwordEncoder.encode(request.newPassword()));
        }

        return new MeResponse(user.getId(), user.getUsername(), user.getDisplayName(), user.getRole(), user.getCreatedAt());
    }
}
