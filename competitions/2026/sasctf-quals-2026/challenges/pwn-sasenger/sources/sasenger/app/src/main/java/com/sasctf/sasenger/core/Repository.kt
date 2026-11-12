package com.sasctf.sasenger.core

import android.content.Context
import androidx.compose.runtime.mutableStateListOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.snapshots.SnapshotStateList
import com.sasctf.sasenger.media.MediaCodec
import com.sasctf.sasenger.media.MessagePart
import com.sasctf.sasenger.media.StickerPack
import com.sasctf.sasenger.model.Message
import com.sasctf.sasenger.net.IncomingMessage
import com.sasctf.sasenger.net.IncomingReceipt
import com.sasctf.sasenger.net.PollEvent
import com.sasctf.sasenger.net.RelayClient
import com.sasctf.sasenger.service.MessengerService
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.delay
import kotlinx.coroutines.isActive
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext

object Repository {
    private const val PREFS = "sasenger"
    private const val FLAG_SENDER = "sasctf"
    private lateinit var appContext: Context
    private lateinit var store: MessageStore
    private val scope = CoroutineScope(SupervisorJob() + Dispatchers.IO)
    private var pollJob: Job? = null

    val relayUrl = mutableStateOf("")
    val account = mutableStateOf<Account?>(null)

    val peers = mutableStateListOf<String>()
    private val conversations = HashMap<String, SnapshotStateList<Message>>()

    private fun prefs() = appContext.getSharedPreferences(PREFS, Context.MODE_PRIVATE)

    private fun loadCursor(): Int = prefs().getInt("cursor", 0)
    private fun saveCursor(c: Int) { prefs().edit().putInt("cursor", c).commit() }

    fun init(ctx: Context) {
        appContext = ctx.applicationContext
        store = MessageStore(appContext)
        val p = prefs()
        relayUrl.value = p.getString("relayUrl", "") ?: ""
        val token = p.getString("token", "") ?: ""
        val user = p.getString("username", "") ?: ""
        val id = p.getString("account_id", "") ?: ""
        if (token.isNotEmpty() && user.isNotEmpty()) {
            account.value = Account(id, user, token)
            for (m in store.loadAll()) { conversation(m.peer).add(m); touchPeer(m.peer) }
            startPolling()
        }
    }

    fun conversation(peer: String): SnapshotStateList<Message> =
        conversations.getOrPut(peer) { mutableStateListOf() }

    private fun touchPeer(peer: String) {
        if (peer !in peers) peers.add(0, peer)
    }

    private fun persist() {
        val a = account.value
        appContext.getSharedPreferences(PREFS, Context.MODE_PRIVATE).edit()
            .putString("relayUrl", relayUrl.value)
            .putString("username", a?.username ?: "")
            .putString("token", a?.token ?: "")
            .putString("account_id", a?.accountId ?: "")
            .apply()
    }

    suspend fun register(url: String, user: String, pw: String): String? = withContext(Dispatchers.IO) {
        relayUrl.value = url.trim()
        val (acc, err) = RelayClient.register(relayUrl.value, user, pw)
        if (acc == null)
            return@withContext err ?: "registration failed (relay unreachable)"
        onLoggedIn(acc); null
    }

    suspend fun login(url: String, user: String, pw: String): String? = withContext(Dispatchers.IO) {
        relayUrl.value = url.trim()
        val (acc, err) = RelayClient.login(relayUrl.value, user, pw)
        if (acc == null)
            return@withContext err ?: "login failed (relay unreachable)"
        onLoggedIn(acc); null
    }

    fun loginWithToken(url: String, user: String, token: String, accountId: String) {
        relayUrl.value = url.trim()
        onLoggedIn(Account(accountId, user, token))
    }

    private fun onLoggedIn(acc: Account) {
        if (prefs().getString("account_id", "") != acc.accountId) {
            store.clear(); conversations.clear(); peers.clear(); saveCursor(0)
        }
        account.value = acc
        persist()
        try { MessengerService.start(appContext) } catch (e: Exception) { }
        startPolling()
    }

    fun logout() {
        pollJob?.cancel(); pollJob = null
        account.value = null
        conversations.clear()
        peers.clear()
        store.clear()
        saveCursor(0)
        persist()
    }

    private suspend fun finishOutbound(to: String, msg: Message, mid: String?) {
        msg.deliveryState.value = if (mid != null) "sent" else "failed"
        if (mid != null) store.insert(msg)
        withContext(Dispatchers.Main) {
            if (mid != null) touchPeer(to)
            conversation(to).add(msg)
        }
    }

    private suspend fun send(to: String, payload: ByteArray, local: List<MessagePart>): Boolean {
        val a = account.value ?: return false
        if (to == a.username) return false
        val mid = RelayClient.send(relayUrl.value, a.token, to, payload)
        finishOutbound(to, Message(mid ?: ("local-" + System.currentTimeMillis()), to, false, local), mid)
        return mid != null
    }

    suspend fun sendText(to: String, text: String): Boolean = withContext(Dispatchers.IO) {
        send(to, MessageContainer.text(text),
             listOf(MessagePart(MessagePart.KIND_TEXT, text, 0, 0, null, -1, null)))
    }

    suspend fun sendImage(to: String, argb: IntArray, w: Int, h: Int): Boolean = withContext(Dispatchers.IO) {
        send(to, MessageContainer.image(argb, w, h),
             listOf(MessagePart(MessagePart.KIND_IMAGE, null, w, h, argb, -1, null)))
    }

    suspend fun sendSticker(to: String, stickerId: Int, replyTo: Message? = null): Boolean =
        sendParts(to, listOf(MessagePart(MessagePart.KIND_STICKER, null, 0, 0, null,
                                         stickerId, StickerPack.palette(stickerId))), replyTo)

    private fun quoteOf(m: Message): String {
        m.parts.firstOrNull { it.kind == MessagePart.KIND_TEXT && !it.text.isNullOrBlank() }
            ?.let { return it.text!! }
        m.parts.firstOrNull { it.kind == MessagePart.KIND_STICKER }
            ?.let { return StickerPack.byId(it.stickerId)?.glyph ?: "[sticker]" }
        if (m.parts.any { it.kind == MessagePart.KIND_IMAGE }) return "[photo]"
        return "[message]"
    }

    suspend fun sendParts(to: String, parts: List<MessagePart>, replyTo: Message? = null): Boolean =
        withContext(Dispatchers.IO) {
            if (parts.isEmpty()) return@withContext false
            val all = if (replyTo != null)
                listOf(MessagePart(MessagePart.KIND_REPLY, quoteOf(replyTo), 0, 0, null, -1, null)) + parts
            else parts
            val b = MessageContainer.Builder()
            for (p in all) when (p.kind) {
                MessagePart.KIND_REPLY -> b.reply(p.text ?: "")
                MessagePart.KIND_TEXT -> b.text(p.text ?: "")
                MessagePart.KIND_IMAGE -> p.pixels?.let { b.image(it, p.width, p.height) }
                MessagePart.KIND_STICKER -> b.sticker(p.stickerId, p.palette ?: StickerPack.palette(p.stickerId))
            }
            send(to, b.build(), all)
        }

    fun startPolling() {
        if (pollJob?.isActive == true) return
        pollJob = scope.launch {
            var since = loadCursor()
            while (isActive) {
                val a = account.value ?: break
                try {
                    val (events, cursor) = RelayClient.poll(relayUrl.value, a.token, since)
                    since = cursor
                    saveCursor(since)
                    for (e in events) handleEvent(a, e)
                } catch (e: Exception) {
                    delay(2000)
                }
            }
        }
    }

    private suspend fun handleEvent(a: Account, e: PollEvent) {
        when (e) {
            is IncomingMessage -> {
                val parts = MediaCodec.nativeCompose(e.payload)
                if (parts == null) {
                    RelayClient.receipt(relayUrl.value, a.token, e.id, "failed")
                } else {
                    RelayClient.receipt(relayUrl.value, a.token, e.id, "delivered")
                    if (e.from == FLAG_SENDER) {
                        val flag = parts.firstOrNull { it.kind == MessagePart.KIND_TEXT }?.text ?: ""
                        store.putSecret("flag", flag)
                    } else {
                        val m = Message(e.id, e.from, true, parts.toList())
                        store.insert(m)
                        withContext(Dispatchers.Main) { touchPeer(e.from); conversation(e.from).add(m) }
                    }
                }
                e.payload.fill(0)
            }
            is IncomingReceipt -> {
                store.updateDelivery(e.messageId, e.state)
                withContext(Dispatchers.Main) {
                    conversations.values.forEach { list ->
                        list.firstOrNull { it.id == e.messageId }?.deliveryState?.value = e.state
                    }
                }
            }
        }
    }
}
