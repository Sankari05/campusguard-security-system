package com.watchman.repository;

import com.watchman.model.Student;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Repository;
import java.util.Optional;
import java.util.List;

@Repository
public interface StudentRepository extends JpaRepository<Student, Long> {
    Optional<Student> findByRollNumberIgnoreCase(String rollNumber);
    List<Student> findByDepartment(String department);
}
