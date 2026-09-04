# Publishing checklist

Before publishing the project beyond a private developer environment, complete the following items.

## Required cleanup

- Keep the `.env.example` file in sync with the required environment variables.
- Add automated tests for PDF splitting, fallback summary generation, and upload behavior.
- Review and standardize Python version compatibility. The current `>=3.14` constraint is unusually restrictive for a general developer audience.
- Confirm that no secrets, credentials, or local-only data remain in version control.
- Add CI for linting and smoke checks if this project is used beyond a private workflow.

## Documentation cleanup

- Keep the root README concise and developer-focused.
- Keep the docs folder as the deeper operational reference.
- Remove stale or duplicated design notes once they have been folded into the wiki pages.
- Document the assumptions behind the `Reason for Visit` encounter segmentation heuristic.

## Operational readiness

- Validate the pipeline on a representative set of real PDF records.
- Confirm the template output is stable for your target document types.
- Decide whether Discord notifications are appropriate for alerting or should be replaced with a more formal monitoring channel.
- Consider packaging the project as a proper CLI or service if it will be used outside the current workflow context.
