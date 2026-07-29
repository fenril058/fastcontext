Reads a file from the local filesystem. Only files inside the working directory are reachable; a path
outside it is refused, whether it is given as absolute, as relative, or reached through a symlink.
It is okay to read a file that does not exist; an error will be returned.

Usage:
- You can optionally specify a line offset and limit (especially handy for long files), but it's recommended to read the whole file by not providing these parameters
- Lines in the output are numbered starting at 1, using following format: LINE_NUMBER|LINE_CONTENT
- You have the capability to call multiple tools in a single response, and they run concurrently. It is always better to speculatively read multiple files as a batch that are potentially useful.
- If you read a file that exists but has empty contents you will receive 'File is empty.'
- Any lines longer than 2000 characters will be truncated to 2000 characters with '...' appended to the end.
- Any file content that exceeds the 2000 lines will be truncated to 2000 lines with '...' appended to the end.
