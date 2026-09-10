package com.soufiane.device.security;

import com.soufiane.device.audit.AuditFilter;
import com.soufiane.device.audit.AuditReporter;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.http.HttpMethod;
import org.springframework.security.config.annotation.web.builders.HttpSecurity;
import org.springframework.security.config.annotation.web.configuration.EnableWebSecurity;
import org.springframework.security.config.http.SessionCreationPolicy;
import org.springframework.security.web.SecurityFilterChain;
import org.springframework.security.web.authentication.UsernamePasswordAuthenticationFilter;

// Introduced in step 2, this service had no auth at all before: nginx just
// proxied straight through. Same rule as video-service and ai-service's
// Python middleware: any authenticated role can read, a write needs ADMIN
// or OPERATOR, SERVICE (ai-service's own calls here) is trusted regardless
// of method since it isn't a human role.
@Configuration
@EnableWebSecurity
public class SecurityConfig {

    private final JwtAuthFilter jwtAuthFilter;
    private final RestAuthEntryPoint restAuthEntryPoint;
    private final RestAccessDeniedHandler restAccessDeniedHandler;
    private final AuditReporter auditReporter;

    public SecurityConfig(JwtAuthFilter jwtAuthFilter, RestAuthEntryPoint restAuthEntryPoint,
                           RestAccessDeniedHandler restAccessDeniedHandler, AuditReporter auditReporter) {
        this.jwtAuthFilter = jwtAuthFilter;
        this.restAuthEntryPoint = restAuthEntryPoint;
        this.restAccessDeniedHandler = restAccessDeniedHandler;
        this.auditReporter = auditReporter;
    }

    @Bean
    public SecurityFilterChain filterChain(HttpSecurity http) throws Exception {
        http
                .csrf(csrf -> csrf.disable())
                .sessionManagement(s -> s.sessionCreationPolicy(SessionCreationPolicy.STATELESS))
                .authorizeHttpRequests(auth -> auth
                        // Docker's healthcheck has no token, same as every other service here.
                        .requestMatchers("/actuator/health").permitAll()
                        // Zones: anyone may read them (the device form and filters need
                        // the list), but only ADMIN creates, renames or deletes one.
                        // Assigning a device to a zone is a device write, still OPERATOR.
                        .requestMatchers(HttpMethod.GET, "/api/zones/**").authenticated()
                        .requestMatchers("/api/zones/**").hasRole("ADMIN")
                        .requestMatchers(HttpMethod.GET, "/**").authenticated()
                        .anyRequest().hasAnyRole("ADMIN", "OPERATOR", "SERVICE"))
                .exceptionHandling(ex -> ex
                        .authenticationEntryPoint(restAuthEntryPoint)
                        .accessDeniedHandler(restAccessDeniedHandler))
                .addFilterBefore(jwtAuthFilter, UsernamePasswordAuthenticationFilter.class)
                .addFilterAfter(new AuditFilter(auditReporter), JwtAuthFilter.class);
        return http.build();
    }
}
