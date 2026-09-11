package com.soufiane.auth;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.boot.autoconfigure.security.servlet.UserDetailsServiceAutoConfiguration;

// Auth here is all JWT (JwtAuthFilter), no UserDetailsService involved, so
// this exclusion stops Boot from generating a throwaway user and logging
// its password on every boot.
@SpringBootApplication(exclude = UserDetailsServiceAutoConfiguration.class)
public class AuthApplication {
    public static void main(String[] args) {
        SpringApplication.run(AuthApplication.class, args);
    }
}
