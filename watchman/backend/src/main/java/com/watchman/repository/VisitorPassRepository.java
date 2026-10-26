package com.watchman.repository;

import com.watchman.model.VisitorPass;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Repository;
import java.util.Optional;
import java.util.List;

@Repository
public interface VisitorPassRepository extends JpaRepository<VisitorPass, Long> {
    Optional<VisitorPass> findByOtp(String otp);
    Optional<VisitorPass> findByPassNumber(String passNumber);
    List<VisitorPass> findByStatusOrderByCheckInTimeDesc(String status);
}
