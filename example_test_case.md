# Sample Test Cases for Test Automation Tool

## Example 1: Basic Login Test

**Test Name:** User Login Test
**Description:** Test user login functionality with valid credentials
**Starting URL:** https://example.com/login

### Natural Language Steps:
```
Navigate to https://example.com/login
Type "testuser" into username field
Type "password123" into password field
Click on login button
Verify that welcome message contains "Welcome"
Take screenshot
```

### JSON Steps:
```json
[
    {"action": "navigate", "url": "https://example.com/login"},
    {"action": "fill", "selector": "#username", "text": "testuser"},
    {"action": "fill", "selector": "#password", "text": "password123"},
    {"action": "click", "selector": "button[type='submit']"},
    {"action": "verify_text", "selector": ".welcome", "expected": "Welcome"},
    {"action": "screenshot"}
]
```

### Expected Outcomes:
```
User should be redirected to dashboard
Welcome message should be visible
URL should contain '/dashboard'
```

## Example 2: E-commerce Search Test

**Test Name:** Product Search Test
**Description:** Test product search functionality and filters
**Starting URL:** https://shop.example.com

### Natural Language Steps:
```
Navigate to https://shop.example.com
Type "laptop" into search box
Click on search button
Wait for search results to appear
Verify that page title contains "Search Results"
Click on first product
Verify that product details page is visible
Take screenshot
```

### Expected Outcomes:
```
Search results should display relevant products
Product details page should load correctly
Product price should be visible
Add to cart button should be present
```

## Example 3: Form Submission Test

**Test Name:** Contact Form Test
**Description:** Test contact form submission with validation
**Starting URL:** https://example.com/contact

### Natural Language Steps:
```
Navigate to https://example.com/contact
Fill name field with "John Doe"
Fill email field with "john@example.com"
Fill message field with "This is a test message"
Click submit button
Verify that success message contains "Thank you"
Take screenshot
```

### Expected Outcomes:
```
Form should submit successfully
Success message should be displayed
Page should not show any errors
Email confirmation should be mentioned
```

## How to Use:

1. **Go to the Test Automation tab** in the browser interface
2. **Choose your input method:**
   - Natural Language: Copy the natural language steps above
   - Structured JSON: Copy the JSON steps above
3. **Fill in the test details:**
   - Test Name, Description, Starting URL
   - Expected Outcomes
4. **Create the test case** - it will generate a Playwright script preview
5. **Execute the test** - it will run the steps and capture screenshots/videos
6. **Download the results:**
   - Generated Playwright JavaScript test script
   - Test execution report
   - Screenshots and video recording

## Generated Script Features:

The tool automatically generates:
- Complete Playwright test scripts in JavaScript
- Proper wait strategies and error handling
- Screenshot capture at each step
- Video recording of the entire test
- Detailed assertions based on expected outcomes
- Retry logic for flaky elements
- Page object pattern recommendations