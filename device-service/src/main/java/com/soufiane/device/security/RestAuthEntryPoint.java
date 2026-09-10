package com.soufiane.device.security;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.soufiane.device.exception.ApiError;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import org.springframework.http.MediaType;
import org.springframework.security.core.AuthenticationException;
import org.springframework.security.web.AuthenticationEntryPoint;
import org.springframework.stereotype.Component;

import java.io.IOException;

// Same reasoning as auth-service's RestAuthEntryPoint: Spring's own default
// here is Http403ForbiddenEntryPoint, which would answer "no token at all"
// the same way as "wrong role". This keeps 401 for not authenticated
// distinct from 403 for authenticated but not allowed.
@Component
public class RestAuthEntryPoint implements AuthenticationEntryPoint {

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
