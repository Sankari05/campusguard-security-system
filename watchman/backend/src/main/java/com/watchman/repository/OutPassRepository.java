package com.watchman.repository;

import com.watchman.model.OutPass;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Repository;
import java.util.Optional;
import java.util.List;

@Repository
public interface OutPassRepository extends JpaRepository<OutPass, Long> {
    Optional<OutPass> findByPassCode(String passCode);
    List<OutPass> findByStudentRollNumberOrderByCreatedAtDesc(String rollNumber);
    List<OutPass> findByStatusOrderByCreatedAtDesc(String status);
}
