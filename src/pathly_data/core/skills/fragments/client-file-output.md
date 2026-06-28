## Writing your result to a file

Write your ENTIRE result to EXACTLY this path: `<out_path>`

- Write the file as your **final** action, and write it **once**.
- Do **not** print the result to stdout — stdout is discarded by the host; only the file is read.
- When the file exists and is non-empty, you are done — stop. Do not announce completion in chat.
- **Failure contract:** if you cannot produce the output, write a single line beginning with
  `ERROR:` followed by a short reason to `<out_path>` (and nothing else), so the host surfaces it
  to the user. Never leave a partial or placeholder result.
