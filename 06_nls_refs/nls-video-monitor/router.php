<?php
declare(strict_types=1);

/**
 * PHP built-in server router for CIM Serve Hub.
 * Usage: php -S 127.0.0.1:8765 router.php
 */

$hub = __DIR__;
$cim = realpath($hub . '/../..') ?: ($hub . '/../..');
$uri = rawurldecode(parse_url($_SERVER['REQUEST_URI'] ?? '/', PHP_URL_PATH) ?: '/');

$redirects = [
    '/' => '/index.php',
    '/index.htm' => '/index.php',
    '/plan' => '/plan.html',
    '/licenses.html' => '/licenses.php',
    '/changelog.html' => '/changelog.php',
    '/cim-approved-plan.html' => '/cim-approved-plan.php',
    '/git-review.html' => '/git-review.php',
];

if (isset($redirects[$uri])) {
    header('Location: ' . $redirects[$uri], true, 302);
    exit;
}

$mime = [
    'css' => 'text/css',
    'html' => 'text/html; charset=utf-8',
    'htm' => 'text/html; charset=utf-8',
    'js' => 'application/javascript',
    'json' => 'application/json',
    'md' => 'text/plain; charset=utf-8',
    'txt' => 'text/plain; charset=utf-8',
    'pdf' => 'application/pdf',
    'svg' => 'image/svg+xml',
    'png' => 'image/png',
    'jpg' => 'image/jpeg',
    'jpeg' => 'image/jpeg',
];

function hub_serve_file(string $path, array $mime): void
{
    if (!is_file($path)) {
        http_response_code(404);
        echo 'Not found';
        exit;
    }
    $ext = strtolower(pathinfo($path, PATHINFO_EXTENSION));
    if (isset($mime[$ext])) {
        header('Content-Type: ' . $mime[$ext]);
    }
    readfile($path);
    exit;
}

// Hub-local static / PHP
$hubPath = $hub . $uri;
if ($uri !== '/' && is_file($hubPath)) {
    return false;
}

// CIM archive files at /LICENSE, /fonts/..., etc.
$cimPath = $cim . $uri;
if ($uri !== '/' && is_file($cimPath)) {
    hub_serve_file($cimPath, $mime);
}

http_response_code(404);
echo 'Not found: ' . htmlspecialchars($uri, ENT_QUOTES, 'UTF-8');