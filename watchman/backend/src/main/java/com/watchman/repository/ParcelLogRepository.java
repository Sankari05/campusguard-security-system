package com.watchman.repository;

import com.watchman.model.ParcelLog;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;
import org.springframework.stereotype.Repository;
import java.util.List;

@Repository
public interface ParcelLogRepository extends JpaRepository<ParcelLog, Long> {
    List<ParcelLog> findByStatusOrderByReceivedAtDesc(String status);

    @Query("SELECT p FROM ParcelLog p WHERE LOWER(p.departmentOrHostel) LIKE LOWER(CONCAT('%', :keyword, '%'))")
    List<ParcelLog> findByDepartmentOrHostelContainingIgnoreCase(@Param("keyword") String keyword);
}

