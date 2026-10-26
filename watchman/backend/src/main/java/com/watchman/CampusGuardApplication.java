package com.watchman;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;

@SpringBootApplication
public class CampusGuardApplication {
    public static void main(String[] args) {
        SpringApplication.run(CampusGuardApplication.class, args);
        System.out.println("==================================================");
        System.out.println("🚀 CampusGuard Backend Service Running on Port 8080");
        System.out.println("📘 Multi-Situation Security & Watchman Management");
        System.out.println("==================================================");
    }
}
