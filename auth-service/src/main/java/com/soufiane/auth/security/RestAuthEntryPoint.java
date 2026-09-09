package com.soufiane.auth.security;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.soufiane.auth.exception.ApiError;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import org.springframework.http.MediaType;
import org.springframework.security.core.AuthenticationException;
import org.springframework.security.web.AuthenticationEntryPoint;
import org.springframework.stereotype.Component;

import java.io.IOException;

// Spring Security's own default here is Http403ForbiddenEntryPoint, which
// answers "no token at all" the same way as "wrong role", 403. This makes
// the two cases distinct: 401 for not authenticated, 403 stays reserved for
// authenticated-but-not-allowed once RBAC actually enforces roles.
@Component
public class RestAuthEntryPoint implements AuthenticationEntryPoint {

    // Spring's own configured mapper, not `new ObjectMapper()`: a fresh one
    // writes OffsetDateTime as a raw epoch number instead of the ISO string
    // every other response here uses, an easy inconsistency to miss.
    private final ObjectMapper objectMapper;

    public RestAuthEntryPoint(ObjectMapper objectMapper) {
        this.objectMapper = objectMapper;
    }

    @Override
    public void commence(HttpServletRequest request, HttpServletResponse response,
                          AuthenticationException authException) throws IOException {
        response.setStatus(HttpServletResponse.SC_UNAUTHORIZED);
        response.setContentType(MediaType.APPLICATION_JSON_VALUE);
        ApiError body = ApiError.of(401, "Unauthorized", "authentication required");
        objectMapper.writeValue(response.getWriter(), body);
    }
}
