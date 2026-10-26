package com.watchman.dto;

public class ForgotPasswordRequest {
    private String emailOrUsername;

    public ForgotPasswordRequest() {}

    public String getEmailOrUsername() { return emailOrUsername; }
    public void setEmailOrUsername(String emailOrUsername) { this.emailOrUsername = emailOrUsername; }
}
