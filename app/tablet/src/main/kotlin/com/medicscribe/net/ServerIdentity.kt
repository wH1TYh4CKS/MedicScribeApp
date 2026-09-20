package com.medicscribe.net

/**
 * Classification of the server the app is talking to, for the in-app privacy
 * banner. The point is to show a clinic client, honestly, that the connection
 * goes to a private machine and not a public cloud service.
 *
 * Honesty note: during a remote Tailscale demo this reports "Private · Tailscale"
 * — which is true. It does NOT claim "data never leaves the building"; that only
 * holds for the on-prem production deployment.
 */
data class ServerIdentity(
    val host: String,
    val label: String,
    val isPrivate: Boolean,
)

/**
 * Classify a host (IP or DNS name) into a human banner label. First match wins.
 *
 *  - 10.0.2.2                          -> Local (Android emulator loopback)
 *  - 100.64.0.0 .. 100.127.255.255     -> Private · Tailscale (CGNAT range)
 *  - *.ts.net                          -> Private · Tailscale (MagicDNS)
 *  - 10/8, 192.168/16, 172.16/12       -> Private · LAN (RFC 1918)
 *  - anything else                     -> External (banner turns red)
 */
fun classifyServer(host: String): ServerIdentity {
    val h = host.trim().lowercase()

    if (h == "10.0.2.2") {
        return ServerIdentity(host, "Local (emulator)", isPrivate = true)
    }
    if (h.endsWith(".ts.net") || isTailscaleCgnat(h)) {
        return ServerIdentity(host, "Private · Tailscale", isPrivate = true)
    }
    if (isRfc1918(h)) {
        return ServerIdentity(host, "Private · LAN", isPrivate = true)
    }
    return ServerIdentity(host, "⚠ External", isPrivate = false)
}

/** Tailscale CGNAT block: 100.64.0.0/10 -> second octet 64..127. */
private fun isTailscaleCgnat(host: String): Boolean {
    val o = octets(host) ?: return false
    return o[0] == 100 && o[1] in 64..127
}

/** RFC 1918 private ranges: 10/8, 172.16/12, 192.168/16. */
private fun isRfc1918(host: String): Boolean {
    val o = octets(host) ?: return false
    return when {
        o[0] == 10 -> true
        o[0] == 172 && o[1] in 16..31 -> true
        o[0] == 192 && o[1] == 168 -> true
        else -> false
    }
}

/** Parse a dotted-quad IPv4 string into 4 ints, or null if not an IPv4 literal. */
private fun octets(host: String): IntArray? {
    val parts = host.split(".")
    if (parts.size != 4) return null
    val out = IntArray(4)
    for (i in 0 until 4) {
        val n = parts[i].toIntOrNull() ?: return null
        if (n !in 0..255) return null
        out[i] = n
    }
    return out
}
