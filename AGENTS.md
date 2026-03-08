<!-- AUTO-GENERATED from CLAUDE.md + .claude/rules/ -->
<!-- Do not edit directly. Run: just sync-agents -->


---

# Architecture Decision Records (ADR)

## Check Existing ADRs

Before making architectural or design decisions, scan `docs/decisions/` for existing ADRs:

1. **List file names** — identify potentially relevant ADRs by their slugs
2. **Read only candidate files** — check frontmatter (`status`, `name`, `description`) of slug-matched ADRs
3. **Skip** any ADR with status `폐기됨` or `대체됨`
4. **Read full content** only for confirmed relevant ADRs

Do NOT read all ADR files upfront. If a relevant ADR exists:

- Follow it unless there's a strong reason to change
- If changing: create a new ADR that explicitly supersedes the old one
- Never silently contradict a past ADR

## When to Suggest Writing an ADR

Evaluate using the **PRICE** criteria. If **any** apply, suggest ADR creation:

| Criterion         | Signal                                                        | Example                                       |
| ----------------- | ------------------------------------------------------------- | --------------------------------------------- |
| **P**olicy        | Team convention, process decision, coding standard            | "Use cursor-based pagination"                 |
| **R**eversibility | Hard or costly to undo                                        | DB schema, language choice, auth strategy     |
| **I**mpact        | Affects multiple modules, teams, or many files                | API design pattern, state management approach |
| **C**onstraint    | External business rule, regulation, SLA, 3rd party limitation | "Payments must complete within 100ms"         |
| **E**xception     | Goes against convention, counterintuitive choice              | "Intentionally not using ORM here"            |

When detected: briefly state which PRICE criteria apply, then suggest using the `/adr` skill.

## Do NOT Suggest ADR For

- Routine implementation choices (which variable name, loop vs map)
- Decisions already captured in an existing ADR
- Trivial, easily reversible changes
- Standard patterns that match existing project conventions

---

# API Rules

## Common

### Field Naming

- Boolean: `is/has/can` prefix
- Date: `~At` suffix (ISO 8601 UTC)
- Consistent terminology (unify on "create" or "add", etc.)

### Pagination (Cursor-Based)

- REST: `?cursor=xyz&limit=20` → `{ data, nextCursor, hasNext }`
- GraphQL: Relay Connection (`first`, `after`, `PageInfo`)

### Sorting

- Parameters: `sortBy`, `sortOrder` (REST) or `orderBy` array (GraphQL)
- Support multiple criteria
- Specify defaults clearly

### Filtering

- Range: `{ min, max }` or `{ gte, lte }`
- Complex conditions: nested objects

## REST

- Nested resources: max 2 levels
- Verbs only when not expressible as resource (`/users/:id/activate`)
- List response: `data` + pagination info
- Creation: 201 + resource (exclude sensitive info)
- Error: RFC 7807 ProblemDetail (`type`, `title`, `status`, `detail`, `instance`)
- Batch: `/batch` suffix with success/failure counts

## GraphQL

### Type Naming

- Input: `{Verb}{Type}Input`
- Connection: `{Type}Connection`
- Edge: `{Type}Edge`

### Input Design

- Separate create/update (required vs optional fields)
- Avoid nesting - use IDs only

### Error Handling

- Default: `code`, `field` in `errors[].extensions`
- Type-safe: Union types (`User | ValidationError`)

### Performance

- N+1: DataLoader mandatory

### Documentation

- `"""description"""` required for all types
- State input constraints explicitly
- Deprecation: `@deprecated(reason: "...")`, never delete types

---

# General Rules

## Dependencies

AI tends to use version ranges by default, causing non-reproducible builds.

- Exact versions only - forbid version ranges
  - e.g., `lodash@4.17.21`, `github.com/pkg/errors v0.9.1`
  - Forbid: `^1.0.0`, `~1.0.0`, `>=1.0.0`, `latest`, etc.
- Detect package manager from lock file
- CI must use frozen mode (e.g., `--frozen-lockfile`)
- Prefer task runner commands (just, make) when available

## Naming

AI tends to use vague, generic verbs that obscure what code actually does.

- Clear purpose while being concise
- Forbid abbreviations outside industry standards (id, api, db, err, etc.)
- Don't repeat context from parent scope
- Boolean: `is`, `has`, `should` prefix
- Function names: verbs or verb+noun forms
- Banned verbs: `process`, `handle`, `manage`, `do`, `execute`, etc.
  - Use domain-specific verbs: `validate`, `transform`, `parse`, `dispatch`, `route`, etc.
  - Exception: Event handlers (`onClick`, `handleSubmit`)
- Collections: `users` (array/slice), `userList` (wrapped), `userSet` (specific)
- Field order: alphabetically by default

## Error Handling

AI tends to generate catch-all handlers that silently swallow errors.

- Handle errors where meaningful response is possible
- Error messages: technical details for logs, actionable guidance for users
- Distinguish expected vs unexpected errors
- Add context when propagating errors up the call stack
- Never silently ignore errors
  - Bad: `catch(e) {}`, `if err != nil { return nil }`, etc.
  - Good: Log with context + propagate or recover with fallback
- Create custom error types for domain-specific failures
- Always handle async errors (Promise rejection, etc.)

## Comments

Comments explaining WHAT code does become stale; code should be self-documenting.

- Write only:
  - WHY: Business rules, external constraints, counter-intuitive decisions
  - Constraints: `// Constraint: Must complete within 100ms`
  - Intent: `// Goal: Minimize database round-trips`
  - Side Effects: `// Side effect: Sends email notification`
  - Anti-patterns: `// Intentionally sequential - parallel breaks idempotency`
- Never: WHAT explanations, code narration, section dividers, commented-out code, etc.
- If code needs a WHAT comment, fix the code instead (rename, extract function)

## Code Structure

- One function, one responsibility
  - "and/or" in function name → split into separate functions
  - Multiple test cases per if branch → split
- Max nesting: 2 levels (use early return/guard clause)
- Make side effects explicit in function name
- Magic numbers/strings → named constants
- Function order: by call order (top-to-bottom)
- No code duplication - modularize similar patterns
  - Same file → extract function
  - Multiple files → separate module
  - Multiple projects → separate package
- Use well-tested external libraries for complex logic (security, crypto, etc.)

## Single Source of Truth

AI tends to duplicate definitions across layers, causing sync issues.

- Every data element has exactly one authoritative source
- Schema-first: define schema (Zod/Prisma/OpenAPI) → generate types
  - `type User = z.infer<typeof userSchema>`, not manual interface duplication
- Constants: single definition file, derive enums/schemas from it
- Configuration: one validated config module, fail fast at startup
- API contracts: spec is authoritative, generate server interfaces + client SDK
- Documentation: generate from source (JSDoc, OpenAPI), never maintain separately
- Warning signs: same interface in multiple files, "don't forget to update X when changing Y"

## Workflow

- Never auto-create branch/commit/push - always ask user
- Gather context first
  - Read related files before working
  - Check existing patterns and conventions
  - Don't guess file paths - use search tools
  - Don't guess API contracts - read actual code
- Scope management
  - Assess issue size accurately
  - Avoid over-engineering simple tasks
- Update CLAUDE.md/README.md for major changes only
- If AI repeats same mistake, add explicit ban to CLAUDE.md
- Clean up background processes (dev servers, watchers) after use
- Follow project language convention for all generated content

---

# TypeScript Standards

## Package Management

- Use pnpm as default package manager
- Forbid npm, yarn (prevent lock file conflicts)

## File Structure

### Common for All Files

1. Import statements (grouped)
2. Constant definitions (alphabetically ordered if multiple)
3. Type/Interface definitions (alphabetically ordered if multiple)
4. Main content

### Inside Classes

- Decorators
- private readonly members
- readonly members
- constructor
- public methods (alphabetically ordered)
- protected methods (alphabetically ordered)
- private methods (alphabetically ordered)

### Function Placement in Function-Based Files

- Main exported function
- Additional exported functions (alphabetically ordered, avoid many)
- Helper functions

## Function Writing

### Use Arrow Functions

- Always use arrow functions except for class methods
- Forbid function keyword entirely (exceptions: generator function\*, function hoisting etc. technically impossible cases only)

### Function Arguments: Flat vs Object

- Use flat if single argument or uncertain of future additions
- Use object form for 2+ arguments in most cases. Allow flat form when:
  - All required arguments without boolean arguments
  - All required arguments with clear order (e.g., (width,height), (start,end), (min,max), (from,to))

## Type System

### Type Safety

- Forbid unsafe type bypasses like any, as, !, @ts-ignore, @ts-expect-error
- Exceptions: Missing or incorrect external library types, rapid development needed (clarify reason in comments)
- Allow some unknown type when type guard is clear
- Allow as assertion when literal type (as const) needed
- Allow as assertion when widening literal/HTML types to broader types
- Allow "!" assertion when type narrowing impossible after type guard due to TypeScript limitation
- Allow @ts-ignore, @ts-expect-error in test code (absolutely forbid in production)

### AI Type Safety Enforcement

AI frequently violates type safety for convenience. Require explicit justification:

- **Every `any` needs a comment**: `// any: external API returns untyped response`
- **Every `as` needs a comment**: `// as: narrowing from unknown after validation`
- **Every `!` needs a comment**: `// !: guaranteed by previous null check in line X`
- **Prefer type guards over assertions**: Use `isUser(x)` instead of `x as User`

### Interface vs Type

- Prioritize Type in all cases by default
- Use Interface only for these exceptions:
  - Public API provided to external users like library public API
  - Need to extend existing interface like external libraries
  - Designing OOP-style classes where implementation contract must be clearly defined

### null/undefined Handling

- Actively use Optional Chaining (`?.`)
- Provide defaults with Nullish Coalescing (`??`)
- Distinguish between `null` and `undefined` by semantic meaning:
  - `undefined`: Uninitialized state, optional parameters, value not assigned yet
  - `null`: Intentional absence of value (similar to Go's nil)

## Code Style

### Maintain Immutability

- Use `const` exclusively; `let` only in loops or when reassignment is truly necessary
- Create new values instead of directly modifying arrays/objects
- Use `spread`, `filter`, `map` instead of `push`, `splice`, `sort` (mutates in-place)
- Exceptions: Extremely performance-critical cases (add comment explaining why)

### AI Immutability Enforcement

AI naturally generates mutable code. Apply strict constraints:

- **Forbid**: `array.push()`, `array.splice()`, `array.sort()`, `object.prop = value`
- **Use instead**: `[...array, item]`, `array.filter()`, `[...array].sort()`, `{ ...object, prop: value }`
- **Flag for review**: Any `let` declaration without loop context

## Recommended Libraries

- Testing: Vitest, Playwright
- Utilities: es-toolkit, dayjs
- HTTP: ky, @tanstack/query, @apollo/client
- Form: React Hook Form
- Type validation: zod
- UI: Tailwind + shadcn/ui
- ORM: Prisma (Drizzle if edge support important)
- State management: zustand
- Code formatting: prettier, eslint
- Build: tsup

---

# Testing Core Principles

## Test File Structure

One-to-one matching with the file under test. Test files should be located in the same directory as the target file. File paths should mirror domain structure.

```
# Good: Domain-based organization
src/auth/__tests__/login.test.ts
src/payment/__tests__/checkout.test.ts

# Bad: Flat test directory
tests/test1.test.ts
tests/test2.test.ts
```

## Test Hierarchy

Use nested suite structure to provide domain context. The suite path is the strongest structural signal for understanding test purpose.

```
Good: Rich context in hierarchy, concise test name
  Suite: OrderService > Sorting > "created desc"

Bad: All context crammed into test name
  Test: "OrderService returns items sorted by creation date"
```

Short test names are acceptable when suite context is rich.

## Test Coverage Selection

Omit obvious or overly simple logic (simple getters, constant returns). Prioritize testing business logic, conditional branches, and code with external dependencies.

## AI Test Generation Guidance

AI tends to generate high-coverage but low-insight tests. Apply these constraints:

- **Skip trivial tests**: No tests for simple getters, setters, or pass-through functions
- **Focus AI on high-value areas**: Boundary values, error paths, race conditions, integration points
- **Avoid test bloat**: Each test must provide unique insight not covered by other tests
- **Question AI suggestions**: If AI suggests testing obvious happy paths, request edge cases instead

## Test Case Composition

At least one basic success case is required. Focus primarily on failure cases, boundary values, edge cases, and exception scenarios.

## Test Independence

Each test should be executable independently. No test execution order dependencies. Initialize shared state for each test.

## Given-When-Then Pattern

Structure test code in three stages—Given (setup), When (execution), Then (assertion). Separate stages with comments or blank lines for complex tests.

## Test Data

Use hardcoded meaningful values. Avoid random data as it causes unreproducible failures. Fix seeds if necessary.

## Mocking Principles

Mock external dependencies (API, DB, file system). For modules within the same project, prefer actual usage; mock only when complexity is high.

## Import Real Domain Modules

Import actual services/modules under test by name. Import statements are the strongest signal for understanding what code is being tested.

- Good: Import domain modules (`OrderService`, `PaymentValidator`)
- Bad: Only test utilities imported, or inline everything without imports

## Test Reusability

Extract repeated mocking setups, fixtures, and helper functions into common utilities. Be careful not to harm test readability through excessive abstraction.

## Integration/E2E Testing

Unit tests are the priority. Write integration/E2E tests when complex flows or multi-module interactions are difficult to understand from code alone. Place in separate directories (`tests/integration`, `tests/e2e`).

## Test Naming

Test names should describe behavior, not implementation details.

- Good: `rejects expired tokens with 401 status`, `sorts orders by creation date descending`
- Bad: `test token validation`, `works correctly`, `handles edge case`

Recommended format: "should do X when Y" or direct behavior statement.

## Assertion Count

Multiple related assertions in one test are acceptable, but separate tests when validating different concepts.

---

# TypeScript Testing Standards

## File Naming

Format: `{target-file-name}.spec.ts`

Example: `user.service.ts` → `user.service.spec.ts`

## Test Framework

Use Vitest. Maintain consistency within the project.

## Structure

Use nested `describe` blocks to provide domain context. The suite hierarchy is the strongest structural signal.

```typescript
// Good: Domain > Feature > Scenario hierarchy
describe('AuthService', () => {
  describe('Login', () => {
    it('should authenticate with valid credentials', () => { ... })
    it('should reject invalid password', () => { ... })
  })
  describe('Token', () => {
    it('should refresh expired token', () => { ... })
  })
})

// Bad: Flat structure, no context
test('login works', () => { ... })
test('logout works', () => { ... })
```

## Imports

Import actual domain modules under test. Import statements are the strongest signal for understanding test purpose.

```typescript
// Good: Clear domain imports
import { OrderService } from "@/modules/order";
import { PaymentValidator } from "@/validators/payment";

// Bad: Only test utilities, no domain context
import { render } from "@/test-utils";
```

## Mocking

Utilize Vitest's `vi.mock()`, `vi.spyOn()`. Mock external modules at the top level; change behavior per test with `mockReturnValue`, `mockImplementation`.

## Async Testing

Use `async/await`. Test Promise rejection with `await expect(fn()).rejects.toThrow()` form.

## Setup/Teardown

Use `beforeEach`, `afterEach` for common setup/cleanup. Use `beforeAll`, `afterAll` only for heavy initialization (DB connection, etc.).

## Type Safety

Type check test code too. Minimize `as any` or `@ts-ignore`. Use type guards or type assertions explicitly when needed.

## Test Utils Location

For single-file use, place at bottom of same file. For multi-file sharing, use `__tests__/utils` or `test-utils` directory.

## Coverage

Code coverage is a reference metric. Focus on meaningful test coverage rather than blindly pursuing 100%.
