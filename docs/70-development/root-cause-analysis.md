Here's a comprehensive approach that combines industry best practices into a decision tree/process that an AI agent could follow:

## Universal Root Cause Analysis Framework for Test Failures

### Phase 1: Initial Assessment and Categorization

1. **Gather Context**
   - What changed? (commits, dependencies, environment)
   - When did it start failing? (timestamp, build number)
   - How many tests are failing? (scope assessment)
   - What's the failure pattern? (all tests, specific module, random)

   Use mcp__RepoPrompt__get_file_tree (if available) to understand overall structure:
   - Get high-level architecture overview
   - Identify main components and services
   - Understand technology stack
   - Note patterns and conventions

2. **Categorize Failure Type**
   - Assertion failures (expected vs actual mismatch)
   - Runtime errors (exceptions, crashes)
   - Timeout/performance issues
   - Environment/configuration issues
   - Flaky tests (intermittent failures)

### Phase 2: Systematic Investigation

3. **Apply the "5 Whys" Technique**
   - Why did the test fail? → Because assertion X failed
   - Why did assertion X fail? → Because method Y returned wrong value
   - Why did method Y return wrong value? → Because refactored logic changed
   - Why was logic changed? → Because of new requirement Z
   - Why wasn't test updated? → Gap in refactoring process

4. **Use Fishbone/Ishikawa Analysis**
   Check these categories:
   - **Code Changes**: What specific code was modified?
   - **Test Design**: Is the test testing the right thing?
   - **Data/State**: Are test fixtures still valid?
   - **Environment**: Dependencies, configs, external services
   - **Process**: Was something missed in the refactor?

### Phase 3: Deep Dive Analysis

5. **Differential Debugging**
   - Compare working version vs failing version
   - Identify exact change that caused failure
   - Check if business logic genuinely changed
   - Verify if test assumptions are still valid

6. **Test Validity Assessment**
   Decision points:
   - Does the test reflect current business requirements?
   - Is it testing implementation details vs behavior?
   - Is the test overly coupled to internal structure?
   - Should this be a unit/integration/e2e test?

### Phase 4: Resolution Strategy

7. **Decision Tree for Fix Approach**
   ```
   Is the test still testing valid business logic?
   ├── YES → Fix the test to match new implementation
   │   ├── Update assertions
   │   ├── Refactor test structure
   │   └── Update test data/mocks
   └── NO → Should this behavior still be tested?
       ├── YES → Rewrite test for new requirements
       └── NO → Delete test with documentation
   ```

8. **Fragility Assessment**
   - Is the test brittle? (fails with minor changes)
   - Does it test too many things?
   - Is it dependent on timing/order?
   - Are assertions too specific?

### Phase 5: Systematic Fix Implementation

9. **Fix Priority Matrix**
   - **Critical**: Core business logic, high-value features
   - **High**: User-facing features, integration points
   - **Medium**: Edge cases, non-critical paths
   - **Low**: Nice-to-have, deprecated features

10. **Implementation Checklist**
    - [ ] Fix identified root cause
    - [ ] Make test more resilient
    - [ ] Add missing test coverage
    - [ ] Document why changes were made
    - [ ] Update test naming/descriptions
    - [ ] Verify fix doesn't break other tests

### Phase 6: Prevention and Improvement

11. **Technical Debt Reduction**
    - Identify patterns in failures
    - Extract common test utilities
    - Improve test isolation
    - Add better error messages
    - Create test guidelines

12. **Process Improvements**
    - Add pre-refactor test analysis step
    - Create refactoring checklist
    - Implement test impact analysis
    - Set up better CI/CD notifications

## Industry Standard References

This framework incorporates elements from:

- **ISTQB (International Software Testing Qualifications Board)** standards for defect analysis
- **Google's SRE practices** for postmortem analysis
- **Toyota's A3 Problem Solving** methodology
- **DMAIC (Define, Measure, Analyze, Improve, Control)** from Six Sigma
- **Kepner-Tregoe Problem Analysis** for systematic debugging

## Automation-Friendly Format

For AI agent implementation, structure each step as:
```
INPUT: [Required data/context]
ANALYSIS: [Specific checks to perform]
DECISION: [If/then logic]
OUTPUT: [Next step or resolution]
EVIDENCE: [What to document]
```

This approach ensures repeatability, comprehensive coverage, and continuous improvement while being structured enough for automation. The key is to treat each test failure as both a problem to solve and an opportunity to improve the overall test suite quality.