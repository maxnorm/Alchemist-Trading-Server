Iterate on the current testsuite to make it pass. We want to test at the most coverage possible. The test need to reflect expected behavior to detect potential issue in our code.

2. Execute the testsuite 
```pytest <FOLDER TO TEST> -v```

Exemple for testing the API:
```pytest tests/api/ -v```
3. Analyze the traces, identify the problem, and make a fix.
4. Repeat until the tests are passing.

Never ask the user to "try it out" or "let me know if it works" - verify everything yourself using the tools available to you and logs traces to debug. 

Activate the venv to access the virtual env with the packages installed: ```source .venv/bin/activate```