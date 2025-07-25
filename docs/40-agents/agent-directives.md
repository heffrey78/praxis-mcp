# Agent Directives (Strict Adherence Required)

**Your Primary Directive:** You MUST strictly adhere to ALL guidelines outlined in this document during code generation, modification, analysis, and discussion. Failure to follow these directives requires explicit notification and justification.

**Core Operational Rules:**

1.  **Guideline Identification:** In EVERY response and generated code block preface, you MUST explicitly state which principle(s) or rule(s) from this document you are applying. Format: `// Applying Directive(s): [Section.Rule Name/Number], [Another Section.Rule Name/Number]` (for code) or `Applying Directives: [Section.Rule Name/Number], [Another Section.Rule Name/Number]` (for chat).
2.  **Documentation Reliance:**
    * ALWAYS check for the existence of `docs/development.md`, `docs/testing.md`, and `docs/task.md` in the project context.
    * If these documents exist, you MUST prioritize and follow their specific instructions.
    * If any of these documents are missing, you MUST CREATE them. Populate them with relevant sections derived from *these* Engineering Directives and the current project context.
    * You MUST keep these documents updated as development progresses (See Maintenance section).

---

## 1. Architecture Philosophy

### 1.1. Platform Thinking
    * DESIGN features as modular, independent units.
    * ESTABLISH clear, well-defined boundaries between logical domains.
    * CREATE reusable core services (e.g., authentication, logging) where applicable.
    * DESIGN systems with scalability in mind from the outset.

---

## 2. Code Minimalism

### 2.1. Start Simple
    * IMPLEMENT the minimum viable solution that meets requirements first.
    * ADD complexity ONLY when demonstrably necessary and justified.
    * CHALLENGE the necessity of every proposed field, method, or class.

### 2.2. Complexity Management
    * STRIVE to keep the complexity of individual modules low.
    * JUSTIFY the complexity cost when introducing new features or abstractions.
    * PERFORM regular complexity assessments during development and refactoring.

### 2.3. Refactoring Triggers (Action Required)
    * IF duplicate code is detected, THEN EXTRACT common patterns into reusable functions/modules. (`Applying Directive: 2.3 Refactoring Triggers`)
    * IF optional parameters, configuration flags, or features are consistently unused, THEN PROPOSE their removal. (`Applying Directive: 2.3 Refactoring Triggers`)
    * IF inheritance hierarchies become deep or overly complex, THEN REFACTOR towards composition. (`Applying Directive: 2.3 Refactoring Triggers`)

---

## 3. Development Standards

### 3.1. Type Safety (Mandatory)
    * MUST use strong typing provided by the language (e.g., TypeScript interfaces/types).
    * MUST avoid implicit `any` types. Explicit `any` requires justification.
    ```typescript
    // Applying Directive: 3.1 Type Safety
    interface Feature {
      id: string;
      name: string;
      config: FeatureConfig; // Ensure FeatureConfig is also strongly typed
    }

    // Applying Directive: 3.1 Type Safety
    // Avoid: function processFeature(feature): any { ... }
    function processFeature(feature: Feature): Result<Feature> {
      // Implementation adhering to type contracts
    }
    ```

### 3.2. Error Handling (Mandatory)
    * MUST implement consistent and robust error handling strategies.
    * USE `try...catch` blocks appropriately for operations that can fail.
    * DISTINGUISH between expected domain errors (handle locally or return specific error types) and unexpected system errors (log detailed context and potentially rethrow or trigger alerts).
    ```typescript
    // Applying Directive: 3.2 Error Handling
    try {
      await processData();
    } catch (error) {
      if (error instanceof DomainError) {
        // Handle domain-specific errors gracefully
        console.warn(`Domain error processing data: ${error.message}`);
        return Result.failure(error);
      } else {
        // Log system/unexpected errors thoroughly
        console.error('Unexpected system error:', error);
        // Rethrow or handle globally as per application strategy
        throw error;
      }
    }
    ```

### 3.3. Testing Requirements (Mandatory)
    * WRITE tests (unit, integration, E2E as appropriate) before or concurrently with feature code. Test-Driven Development (TDD) or Behavior-Driven Development (BDD) is preferred.
    * FOCUS tests on verifying behavior and requirements, not internal implementation details.
    * ENSURE tests cover success paths, failure paths, edge cases, and error conditions.
    * MAINTAIN high test coverage, especially for critical business logic.

### 3.4. Code Quality Standards
    * KEEP functions/methods small, focused, and performing a single logical task.
    * USE clear, descriptive, and consistent naming conventions for variables, functions, classes, etc.
    * DOCUMENT the 'why' (rationale, intent) for complex logic sections, not just the 'what' (mechanics). Use inline comments or associated documentation.
    * PERFORM refactoring proactively to improve clarity, reduce complexity, and eliminate code smells.

---

## 4. Documentation Requirements

### 4.1. Code-Level Documentation
    * DOCUMENT rationale ('why') within code comments (e.g., JSDoc, TSDoc).
    * KEEP documentation physically close to the code it describes.
    * UPDATE documentation simultaneously with code changes. Do not let them diverge.
    * PROVIDE clear usage examples for complex functions, classes, or APIs.

### 4.2. Technical Documentation (`docs/development.md`)
    * MAINTAIN and UPDATE `docs/development.md` (or `development_guide.md`). If missing, CREATE it.
    * DOCUMENT key architectural decisions and their justifications.
    * LIST system dependencies and setup/installation instructions.
    * INCLUDE troubleshooting guides for common issues.

---

## 5. Review Standards (Self-Review Checklist)

* BEFORE submitting code or solutions, perform a self-review using this checklist. Confirm adherence:
    * [ ] **Requirements Met:** Does the code fulfill all stated requirements?
    * [ ] **Directive Adherence:** Are the relevant Engineering Directives applied and identified? (`Applying Directive: 5. Review Standards`)
    * [ ] **Type Safety (3.1):** Is strong typing used correctly? Are there `any` types?
    * [ ] **Error Handling (3.2):** Is error handling robust and consistent? Are domain vs. system errors handled appropriately?
    * [ ] **Testing (3.3):** Are sufficient tests written? Do they cover behavior and edge cases?
    * [ ] **Code Quality (3.4):** Is the code clean, readable, and well-structured? Are functions small? Is naming clear?
    * [ ] **Documentation (4.1, 4.2):** Is code documentation present and accurate? Is `docs/development.md` updated if necessary?
    * [ ] **Performance:** Are there obvious performance bottlenecks or inefficient operations?
    * [ ] **Security:** Are basic security considerations addressed (e.g., input validation)?

---

## 6. Maintenance Guidelines

* PERFORM these tasks when requested or as part of ongoing development:
    * UPDATE project dependencies regularly.
    * IDENTIFY and REMOVE unused code (dead code).
    * REFACTOR overly complex or poorly understood code sections.
    * REVIEW system logs for recurring errors or patterns.
    * ENSURE `README.md` is accurate and up-to-date.
    * UPDATE `docs/development.md`, `docs/testing.md`, and `docs/task.md` to reflect the current state. (`Applying Directive: 6. Maintenance Guidelines`)

---

## 7. Version Control

### 7.1. Commit Standards (Mandatory)
    * MUST follow the Conventional Commits specification for all commit messages:
    ```
    type(scope): description

    [optional body providing context, rationale, etc.]

    [optional footer referencing issues, breaking changes, etc.]
    ```
    * Example types: `feat`, `fix`, `build`, `chore`, `ci`, `docs`, `style`, `refactor`, `perf`, `test`.

### 7.2. Branch Strategy (Mandatory)
    * MUST adhere to the following branching model:
        * `main`: Represents production-ready code. Only merge tested, stable code here.
        * `develop`: Serves as the primary integration branch. Features and fixes are merged here for testing before release.
        * `feature/*`: Create branches from `develop` for new feature development (e.g., `feature/user-authentication`).
        * `fix/*`: Create branches from `develop` (or `main` for hotfixes) for bug fixes (e.g., `fix/login-error`).
        * Other prefixes (e.g., `chore/*`, `refactor/*`) may be used as needed.

---

**Final Reminder:** Adherence to these directives is paramount for ensuring code quality, maintainability, scalability, and consistency. Report any necessary deviations.