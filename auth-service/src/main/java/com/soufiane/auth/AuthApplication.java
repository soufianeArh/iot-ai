package com.soufiane.auth;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.boot.autoconfigure.security.servlet.UserDetailsServiceAutoConfiguration;

// UserDetailsServiceAutoConfiguration excluded: nothing here uses Spring's
// UserDetailsService, auth is entirely JWT based (JwtAuthFilter). Without
// this exclusion Spring Boot still generates a throwaway in-memory user and
// logs its password on every boot, dead code that's just confusing noise.
@SpringBootApplication(exclude = UserDetailsServiceAutoConfiguration.class)
public class AuthApplication {
    public static void main(String[] args) {
        SpringApplication.run(AuthApplication.class, args);
    }
}
