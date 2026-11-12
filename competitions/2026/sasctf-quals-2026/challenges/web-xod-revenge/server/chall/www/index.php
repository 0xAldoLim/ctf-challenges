<?php

header("Content-Security-Policy: default-src 'self' 'unsafe-eval'; style-src 'unsafe-inline'");

if (!isset($_GET['dns']) || !is_string($_GET['dns'])) {
    highlight_file(__FILE__);
    exit();
}

// DoH
$dnsQuery = base64_decode($_GET['dns'], true);
if ($dnsQuery === false) {
    http_response_code(400);
    exit('Invalid base64 encoding in "dns" parameter.');
}

$socket = @stream_socket_client("udp://1.1.1.1:53", timeout:1);
if (!$socket) {
    http_response_code(502);
    exit('Error: Could not connect to DNS server.');
}

stream_set_timeout($socket, 1);
fwrite($socket, $dnsQuery);
$response = fread($socket, 4096);
fclose($socket);

if ($response === false || $response === '') {
    http_response_code(500);
    exit('Failed to retrieve a DNS response.');
}

$accept = isset($_SERVER['HTTP_ACCEPT']) ? $_SERVER['HTTP_ACCEPT'] : 'application/dns-message';
header("Content-Type: $accept");

echo $response;