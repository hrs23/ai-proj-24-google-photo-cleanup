<engineering_best_practices>

<code>
- Maintain consistency with existing code wherever possible:
    - Code style
    - Comments
    - Logs
    - Libraries
    - Unit tests
        - Granularity
        - Test naming conventions
    - Letter casing
    - Snake_case vs camelCase
- Remove unused code
- Use pure functions (no side effects, always return the same output for the same input)
- Do not modify arguments directly (return a new object instead)
- Use Stream APIs (map, filter, reduce, etc.) for data processing
- Separate logic from I/O (pure logic should remain clean and easy to test)
- Follow SOLID principles
- Fail fast 
	- Do NOT write unnecessary fallback. We want to detect the issue early.
</code>

<configuration>
- Write generic code so it works seamlessly when configuration changes.
- Follow the SSOT (Single Source of Truth) principle.
</configuration>

<unit-test>
- Always add or update unit tests
- Avoid creating fragile tests
- Do not modify tests just to make them pass
- Unit tests must not affect production
</unit-test>

<manual-test>
- After completing a task, perform a simple manual test to confirm end-to-end functionality.
</manual-test>

<tdd>
- Follow the Red -> Green -> Refactor cycle:
    - Red: Write a failing test (always write the test before implementation)
    - Green: Write the minimal implementation needed to pass the test (focus only on passing)
    - Refactor: After passing, clean up and improve the code (no adding new functionality)
- Repeat this cycle to achieve clean, working code
</tdd>

<documentation>
- Use Markdown when adding documentation to the repository
- Keep documentation minimal and avoid duplication across files
- Only include truly useful information:
    - Do not include content that changes frequently over time
    - Do not document things that are obvious from reading the source code
</documentation>


<post-task-action>
- Refactor the code  
- Clean up unnecessary files and empty folders  
- Update the .gitignore file  
- Verify that all tests pass  
  - Never leave failing tests unresolved!!  
- Update all documentation
</instructions>

</engineering_best_practices>