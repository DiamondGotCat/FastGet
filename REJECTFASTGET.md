# RejectFastGet HTTP Response Header

FastGet now supports the `RejectFastGet` HTTP response header that allows servers to disable parallel downloads.

## Usage

When a server wants to prevent FastGet from using parallel downloads, it can include the `RejectFastGet` header in its HTTP response:

```http
HTTP/1.1 200 OK
Content-Length: 10485760
Accept-Ranges: bytes
RejectFastGet: true
```

## Supported Values

The following values will cause FastGet to fall back to single-threaded downloads:
- `RejectFastGet: true`
- `RejectFastGet: 1` 
- `RejectFastGet: yes`

All values are case-insensitive.

Any other value (including `false`, `0`, `no`) or the absence of the header will allow normal FastGet behavior.

## Server Implementation Examples

### Apache (.htaccess)
```apache
Header set RejectFastGet "true"
```

### Nginx
```nginx
add_header RejectFastGet "true";
```

### Express.js (Node.js)
```javascript
app.get('/download/*', (req, res) => {
    res.set('RejectFastGet', 'true');
    // ... rest of download logic
});
```

### PHP
```php
header('RejectFastGet: true');
```

## Behavior

When FastGet detects the `RejectFastGet` header:
1. It will display: "Server has rejected FastGet parallel downloads. Downloading in single thread..."
2. It will force the number of threads to 1
3. The download will proceed using a single connection
4. This takes precedence over range support checks

This allows servers to:
- Reduce server load during peak times
- Prevent abuse from too many parallel connections
- Maintain control over how their content is downloaded
- Provide a better experience for all users