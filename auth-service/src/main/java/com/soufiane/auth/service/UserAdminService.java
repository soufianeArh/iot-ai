package com.soufiane.auth.service;

import com.soufiane.auth.dto.CreateUserRequest;
import com.soufiane.auth.dto.MeResponse;
import com.soufiane.auth.dto.UpdateUserRequest;
import com.soufiane.auth.entity.User;
import com.soufiane.auth.exception.DuplicateUsernameException;
import com.soufiane.auth.exception.LastAdminException;
import com.soufiane.auth.exception.UserNotFoundException;
import com.soufiane.auth.repository.UserRepository;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.List;

// Admin only, gated in SecurityConfig, not here: this service assumes
// whoever is calling has already been checked for the ADMIN role.
@Service
public class UserAdminService {

    private final UserRepository userRepository;
    private final PasswordEncoder passwordEncoder;

    public UserAdminService(UserRepository userRepository, PasswordEncoder passwordEncoder) {
        this.userRepository = userRepository;
        this.passwordEncoder = passwordEncoder;
    }

    public List<MeResponse> list() {
        return userRepository.findAll().stream().map(UserAdminService::toResponse).toList();
    }

    @Transactional
    public MeResponse create(CreateUserRequest request) {
        userRepository.findByUsername(request.username())
                .ifPresent(u -> { throw new DuplicateUsernameException(request.username()); });

        User user = new User(request.username(), passwordEncoder.encode(request.password()),
                request.displayName(), request.role());
        return toResponse(userRepository.save(user));
    }

    @Transactional
    public MeResponse update(Long id, UpdateUserRequest request) {
        User user = userRepository.findById(id).orElseThrow(() -> new UserNotFoundException(id));

        if (request.role() != null && !request.role().equals(user.getRole())) {
            guardLastAdmin(user);
            user.setRole(request.role());
        }
        if (request.displayName() != null && !request.displayName().isBlank()) {
            user.setDisplayName(request.displayName());
        }
        if (request.newPassword() != null && !request.newPassword().isBlank()) {
            user.setPasswordHash(passwordEncoder.encode(request.newPassword()));
        }
        return toResponse(user);
    }

    @Transactional
    public void delete(Long id) {
        User user = userRepository.findById(id).orElseThrow(() -> new UserNotFoundException(id));
        guardLastAdmin(user);
        userRepository.delete(user);
    }

    // Only matters when the target IS currently an admin and removing that
    // status (by role change or deletion) would leave zero admins.
    private void guardLastAdmin(User user) {
        if ("ADMIN".equals(user.getRole()) && userRepository.countByRole("ADMIN") <= 1) {
            throw new LastAdminException();
        }
    }

    private static MeResponse toResponse(User user) {
        return new MeResponse(user.getId(), user.getUsername(), user.getDisplayName(), user.getRole(), user.getCreatedAt());
    }
}
