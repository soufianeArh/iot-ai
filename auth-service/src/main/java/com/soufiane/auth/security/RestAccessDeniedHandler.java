package com.soufiane.auth.security;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.soufiane.auth.exception.ApiError;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import org.springframework.http.MediaType;
import org.springframework.security.access.AccessDeniedException;
import org.springframework.security.web.access.AccessDeniedHandler;
import org.springframework.stereotype.Component;

import java.io.IOException;

// Spring's own default here writes a bare 403 with no body. This matches the
// ApiError shape every other error response already uses, same reasoning as
// RestAuthEntryPoint for the 401 case: authenticated but not allowed, versus
// not authenticated at all.
@Component
public class RestAccessDeniedHandler implements AccessDeniedHandler {

    private final ObjectMapper objectMapper;

    public RestAccessDeniedHandler(ObjectMapper objectMapper) {
        this.objectMapper = objectMapper;
    }

    @Override
    public void handle(HttpServletRequest request, HttpServletResponse response,
                        AccessDeniedException accessDeniedException) throws IOException {
        response.setStatus(HttpServletResponse.SC_FORBIDDEN);
        response.setContentType(MediaType.APPLICATION_JSON_VALUE);
        ApiError body = ApiError.of(403, "Forbidden", "you do not have permission for this action");
        objectMapper.writeValue(response.getWriter(), body);
    }
}
