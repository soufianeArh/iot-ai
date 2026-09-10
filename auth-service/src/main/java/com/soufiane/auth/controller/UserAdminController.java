package com.soufiane.auth.controller;

import com.soufiane.auth.dto.CreateUserRequest;
import com.soufiane.auth.dto.MeResponse;
import com.soufiane.auth.dto.UpdateUserRequest;
import com.soufiane.auth.service.UserAdminService;
import jakarta.validation.Valid;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.DeleteMapping;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.PutMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.ResponseStatus;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.util.UriComponentsBuilder;

import java.util.List;

// ADMIN only, enforced in SecurityConfig (/api/auth/users/** requires the
// ADMIN role), not repeated here.
@RestController
@RequestMapping("/api/auth/users")
public class UserAdminController {

    private final UserAdminService userAdminService;

    public UserAdminController(UserAdminService userAdminService) {
        this.userAdminService = userAdminService;
    }

    @GetMapping
    public List<MeResponse> list() {
        return userAdminService.list();
    }

    @PostMapping
    public ResponseEntity<MeResponse> create(@Valid @RequestBody CreateUserRequest request,
                                              UriComponentsBuilder uriBuilder) {
        MeResponse created = userAdminService.create(request);
        return ResponseEntity
                .created(uriBuilder.path("/api/auth/users/{id}").build(created.id()))
                .body(created);
    }

    @PutMapping("/{id}")
    public MeResponse update(@PathVariable Long id, @Valid @RequestBody UpdateUserRequest request) {
        return userAdminService.update(id, request);
    }

    @DeleteMapping("/{id}")
    @ResponseStatus(HttpStatus.NO_CONTENT)
    public void delete(@PathVariable Long id) {
        userAdminService.delete(id);
    }
}
