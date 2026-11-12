package com.sasctf.sasenger.net

import android.util.Base64
import com.sasctf.sasenger.core.Account
import org.json.JSONArray
import org.json.JSONObject
import java.net.HttpURLConnection
import java.net.URL

sealed class PollEvent
class IncomingMessage(
    val id: String, val from: String, val payload: ByteArray,
) : PollEvent()
class IncomingReceipt(
    val messageId: String, val from: String, val state: String, val meta: String?,
) : PollEvent()

object RelayClient {

    private fun conn(base: String, path: String, method: String, token: String?): HttpURLConnection {
        val c = URL(base.trimEnd('/') + path).openConnection() as HttpURLConnection
        c.requestMethod = method
        c.connectTimeout = 5000
        c.readTimeout = 40000
        if (token != null) c.setRequestProperty("Authorization", "Bearer $token")
        return c
    }

    private fun readJson(c: HttpURLConnection): Pair<Int, JSONObject> {
        val code = c.responseCode
        val s = (if (code in 200..299) c.inputStream else c.errorStream)
            ?.bufferedReader()?.use { it.readText() } ?: ""
        return Pair(code, if (s.isBlank()) JSONObject() else JSONObject(s))
    }

    private fun postJson(base: String, path: String, body: JSONObject, token: String?): Pair<Int, JSONObject> {
        val c = conn(base, path, "POST", token)
        c.doOutput = true
        c.setRequestProperty("Content-Type", "application/json")
        c.outputStream.use { it.write(body.toString().toByteArray()) }
        return readJson(c)
    }

    private fun accountOf(j: JSONObject) =
        Account(j.optString("account_id"), j.optString("username"), j.optString("token"))

    fun register(base: String, username: String, password: String): Pair<Account?, String?> = try {
        val (code, j) = postJson(base, "/v1/register",
            JSONObject().put("username", username).put("password", password), null)
        if (code in 200..299) accountOf(j) to null else null to errorOf(j)
    } catch (e: Exception) { null to null }

    fun login(base: String, username: String, password: String): Pair<Account?, String?> = try {
        val (code, j) = postJson(base, "/v1/login",
            JSONObject().put("username", username).put("password", password), null)
        if (code in 200..299) accountOf(j) to null else null to errorOf(j)
    } catch (e: Exception) { null to null }

    private fun errorOf(j: JSONObject): String? =
        j.optString("error", "").ifBlank { null }

    fun send(base: String, token: String, to: String, payload: ByteArray): String? = try {
        val msg = JSONObject().put("to", to)
            .put("payload_b64", Base64.encodeToString(payload, Base64.NO_WRAP))
        val (code, j) = postJson(base, "/v1/send", msg, token)
        if (code in 200..299) j.optString("message_id") else null
    } catch (e: Exception) { null }

    fun receipt(base: String, token: String, messageId: String, state: String) {
        try {
            postJson(base, "/v1/receipt",
                JSONObject().put("message_id", messageId).put("state", state), token)
        } catch (e: Exception) { }
    }

    fun poll(base: String, token: String, since: Int): Pair<List<PollEvent>, Int> {
        val c = conn(base, "/v1/poll?since=$since", "GET", token)
        val (_, j) = readJson(c)
        val out = ArrayList<PollEvent>()
        val arr = j.optJSONArray("events") ?: JSONArray()
        for (i in 0 until arr.length()) {
            val e = arr.getJSONObject(i)
            when (e.optString("type")) {
                "message" -> {
                    val payload = Base64.decode(e.optString("payload_b64"), Base64.DEFAULT)
                    out.add(IncomingMessage(e.optString("id"), e.optString("from"), payload))
                }
                "receipt" -> out.add(IncomingReceipt(
                    e.optString("message_id"), e.optString("from"), e.optString("state"),
                    if (e.isNull("meta")) null else e.optString("meta")))
            }
        }
        return Pair(out, j.optInt("cursor", since))
    }
}
