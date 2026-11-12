package com.sasctf.sasenger.ui

import android.content.Context
import android.graphics.Bitmap
import android.graphics.ImageDecoder
import android.net.Uri
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.PickVisualMediaRequest
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.ExperimentalFoundationApi
import androidx.compose.foundation.Image
import androidx.compose.foundation.background
import androidx.compose.foundation.combinedClickable
import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.layout.widthIn
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.lazy.rememberLazyListState
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material.icons.automirrored.filled.Reply
import androidx.compose.material.icons.automirrored.filled.Send
import androidx.compose.material.icons.filled.AttachFile
import androidx.compose.material.icons.filled.Check
import androidx.compose.material.icons.filled.Close
import androidx.compose.material.icons.filled.DoneAll
import androidx.compose.material.icons.filled.ErrorOutline
import androidx.compose.material.icons.filled.Mood
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.material3.TextField
import androidx.compose.material3.TextFieldDefaults
import androidx.compose.material3.TopAppBar
import androidx.compose.material3.TopAppBarDefaults
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateListOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.asImageBitmap
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.sasctf.sasenger.core.Repository
import com.sasctf.sasenger.media.MessagePart
import com.sasctf.sasenger.media.StickerPack
import com.sasctf.sasenger.model.Message
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun ChatScreen(peer: String, onBack: () -> Unit) {
    val scope = rememberCoroutineScope()
    val ctx = LocalContextOrNull()
    val msgs = Repository.conversation(peer)
    val listState = rememberLazyListState()
    var text by remember { mutableStateOf("") }
    val attach = remember { mutableStateListOf<PendingImage>() }
    var showStickers by remember { mutableStateOf(false) }
    var replyTarget by remember { mutableStateOf<Message?>(null) }

    val picker = rememberLauncherForActivityResult(
        ActivityResultContracts.PickMultipleVisualMedia(8)) { uris ->
        if (uris.isNotEmpty() && ctx != null) scope.launch {
            val decoded = withContext(Dispatchers.IO) { uris.mapNotNull { decodeAttachment(ctx, it) } }
            attach.addAll(decoded)
        }
    }

    LaunchedEffect(msgs.size) {
        if (msgs.isNotEmpty()) listState.animateScrollToItem(msgs.size - 1)
    }

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text(peer, style = MaterialTheme.typography.titleLarge) },
                navigationIcon = {
                    IconButton(onClick = onBack) { Icon(Icons.AutoMirrored.Filled.ArrowBack, "back") }
                },
                colors = TopAppBarDefaults.topAppBarColors(
                    containerColor = MaterialTheme.colorScheme.background),
            )
        },
        containerColor = MaterialTheme.colorScheme.background,
    ) { pad ->
        Column(Modifier.fillMaxSize().padding(pad)) {
            LazyColumn(
                state = listState,
                modifier = Modifier.weight(1f).fillMaxWidth().padding(horizontal = 12.dp),
                contentPadding = PaddingValues(vertical = 8.dp),
                verticalArrangement = Arrangement.spacedBy(6.dp),
            ) {
                items(msgs) { m -> Bubble(m, onReply = { replyTarget = it }) }
            }

            if (attach.isNotEmpty()) {
                Row(
                    Modifier.fillMaxWidth().padding(horizontal = 14.dp, vertical = 4.dp),
                    verticalAlignment = Alignment.CenterVertically,
                ) {
                    Icon(Icons.Filled.AttachFile, null, tint = MaterialTheme.colorScheme.primary,
                        modifier = Modifier.size(18.dp))
                    Spacer(Modifier.width(6.dp))
                    Text("${attach.size} image${if (attach.size == 1) "" else "s"} attached",
                        style = MaterialTheme.typography.labelMedium,
                        color = MaterialTheme.colorScheme.onSurfaceVariant, modifier = Modifier.weight(1f))
                    IconButton(onClick = { attach.clear() }) {
                        Icon(Icons.Filled.Close, "remove", modifier = Modifier.size(18.dp))
                    }
                }
            }

            replyTarget?.let { r ->
                Row(
                    Modifier.fillMaxWidth().padding(horizontal = 14.dp, vertical = 4.dp),
                    verticalAlignment = Alignment.CenterVertically,
                ) {
                    Icon(Icons.AutoMirrored.Filled.Reply, null, tint = MaterialTheme.colorScheme.primary,
                        modifier = Modifier.size(18.dp))
                    Spacer(Modifier.width(6.dp))
                    Text("Replying to: " + quoteLabel(r), style = MaterialTheme.typography.labelMedium,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                        maxLines = 1, overflow = TextOverflow.Ellipsis, modifier = Modifier.weight(1f))
                    IconButton(onClick = { replyTarget = null }) {
                        Icon(Icons.Filled.Close, "cancel reply", modifier = Modifier.size(18.dp))
                    }
                }
            }

            if (showStickers) {
                StickerRow(onPick = { id ->
                    val r = replyTarget; showStickers = false; replyTarget = null
                    scope.launch { Repository.sendSticker(peer, id, r) }
                })
            }

            InputBar(
                text = text,
                onText = { text = it },
                onAttach = { picker.launch(PickVisualMediaRequest(ActivityResultContracts.PickVisualMedia.ImageOnly)) },
                onStickers = { showStickers = !showStickers },
                onSend = {
                    val t = text; val imgs = attach.toList(); val r = replyTarget
                    if (t.isNotBlank() || imgs.isNotEmpty()) {
                        text = ""; attach.clear(); showStickers = false; replyTarget = null
                        scope.launch {
                            val parts = ArrayList<MessagePart>()
                            for (im in imgs) parts.add(
                                MessagePart(MessagePart.KIND_IMAGE, null, im.w, im.h, im.px, -1, null))
                            if (t.isNotBlank()) parts.add(
                                MessagePart(MessagePart.KIND_TEXT, t, 0, 0, null, -1, null))
                            Repository.sendParts(peer, parts, r)
                        }
                    }
                },
            )
        }
    }
}

@OptIn(ExperimentalFoundationApi::class)
@Composable
private fun Bubble(m: Message, onReply: (Message) -> Unit) {
    val out = !m.incoming
    val accent = m.parts.firstNotNullOfOrNull { p ->
        if (p.kind == MessagePart.KIND_STICKER)
            p.palette?.firstOrNull() ?: StickerPack.byId(p.stickerId)?.palette?.firstOrNull()
        else null
    }
    Row(
        Modifier.fillMaxWidth(),
        horizontalArrangement = if (out) Arrangement.End else Arrangement.Start,
    ) {
        Column(
            Modifier
                .widthIn(max = 280.dp)
                .clip(RoundedCornerShape(
                    topStart = 16.dp, topEnd = 16.dp,
                    bottomStart = if (out) 16.dp else 4.dp,
                    bottomEnd = if (out) 4.dp else 16.dp))
                .background(if (out) MaterialTheme.colorScheme.primaryContainer
                           else MaterialTheme.colorScheme.surfaceVariant)
                .background(if (accent != null) Color(accent).copy(alpha = 0.22f) else Color.Transparent)
                .combinedClickable(onClick = {}, onLongClick = { onReply(m) })
                .padding(10.dp),
            verticalArrangement = Arrangement.spacedBy(6.dp),
        ) {
            for (p in m.parts) PartView(p)
            if (out) DeliveryTick(m)
        }
    }
}

@Composable
private fun PartView(p: MessagePart) {
    when (p.kind) {
        MessagePart.KIND_REPLY ->
            Row(verticalAlignment = Alignment.CenterVertically) {
                Box(Modifier.width(3.dp).height(18.dp).clip(RoundedCornerShape(2.dp))
                    .background(MaterialTheme.colorScheme.primary))
                Spacer(Modifier.width(6.dp))
                Text(p.text?.ifBlank { "[message]" } ?: "[message]",
                    style = MaterialTheme.typography.labelMedium,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                    maxLines = 1, overflow = TextOverflow.Ellipsis)
            }
        MessagePart.KIND_TEXT ->
            Text(p.text.orEmpty(), style = MaterialTheme.typography.bodyLarge,
                color = MaterialTheme.colorScheme.onSurface)
        MessagePart.KIND_IMAGE -> {
            val bmp = remember(p) {
                val px = p.pixels
                if (px != null && p.width > 0 && p.height > 0)
                    Bitmap.createBitmap(px, p.width, p.height, Bitmap.Config.ARGB_8888).asImageBitmap()
                else null
            }
            if (bmp != null)
                Image(bmp, "image", contentScale = ContentScale.FillWidth,
                    modifier = Modifier.fillMaxWidth().clip(RoundedCornerShape(8.dp)))
            else
                Text("[photo]", style = MaterialTheme.typography.bodyMedium,
                    color = MaterialTheme.colorScheme.onSurfaceVariant)
        }
        MessagePart.KIND_STICKER ->
            Text(StickerPack.byId(p.stickerId)?.glyph ?: "🎁", fontSize = 44.sp)
    }
}

@Composable
private fun DeliveryTick(m: Message) {
    Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.End,
        verticalAlignment = Alignment.CenterVertically) {
        when (m.deliveryState.value) {
            "delivered" -> Icon(Icons.Filled.DoneAll, "delivered",
                tint = MaterialTheme.colorScheme.primary, modifier = Modifier.size(15.dp))
            "failed" -> Icon(Icons.Filled.ErrorOutline, "failed",
                tint = MaterialTheme.colorScheme.error, modifier = Modifier.size(15.dp))
            else -> Icon(Icons.Filled.Check, "sent",
                tint = MaterialTheme.colorScheme.onSurfaceVariant, modifier = Modifier.size(15.dp))
        }
    }
}

@Composable
private fun StickerRow(onPick: (Int) -> Unit) {
    Row(
        Modifier.fillMaxWidth().horizontalScroll(rememberScrollState())
            .padding(horizontal = 10.dp, vertical = 4.dp),
        horizontalArrangement = Arrangement.spacedBy(4.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        for (s in StickerPack.all) {
            IconButton(onClick = { onPick(s.id) }) { Text(s.glyph, fontSize = 28.sp) }
        }
    }
}

@Composable
private fun InputBar(
    text: String,
    onText: (String) -> Unit,
    onAttach: () -> Unit,
    onStickers: () -> Unit,
    onSend: () -> Unit,
) {
    Row(
        Modifier.fillMaxWidth().padding(horizontal = 8.dp, vertical = 8.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        IconButton(onClick = onStickers) {
            Icon(Icons.Filled.Mood, "stickers", tint = MaterialTheme.colorScheme.onSurfaceVariant)
        }
        IconButton(onClick = onAttach) {
            Icon(Icons.Filled.AttachFile, "attach", tint = MaterialTheme.colorScheme.onSurfaceVariant)
        }
        TextField(
            value = text, onValueChange = onText,
            placeholder = { Text("Message") },
            modifier = Modifier.weight(1f),
            maxLines = 4,
            shape = RoundedCornerShape(22.dp),
            colors = TextFieldDefaults.colors(
                focusedContainerColor = MaterialTheme.colorScheme.surface,
                unfocusedContainerColor = MaterialTheme.colorScheme.surface,
                focusedIndicatorColor = Color.Transparent,
                unfocusedIndicatorColor = Color.Transparent,
            ),
        )
        Spacer(Modifier.width(6.dp))
        IconButton(onClick = onSend) {
            Icon(Icons.AutoMirrored.Filled.Send, "send", tint = MaterialTheme.colorScheme.primary)
        }
    }
}

private fun quoteLabel(m: Message): String {
    m.parts.firstOrNull { it.kind == MessagePart.KIND_TEXT && !it.text.isNullOrBlank() }
        ?.let { return it.text!! }
    m.parts.firstOrNull { it.kind == MessagePart.KIND_STICKER }
        ?.let { return StickerPack.byId(it.stickerId)?.glyph ?: "[sticker]" }
    if (m.parts.any { it.kind == MessagePart.KIND_IMAGE }) return "[photo]"
    return "[message]"
}

private class PendingImage(val px: IntArray, val w: Int, val h: Int)

private fun decodeAttachment(ctx: Context, uri: Uri): PendingImage? = try {
    val src = ImageDecoder.createSource(ctx.contentResolver, uri)
    val bmp = ImageDecoder.decodeBitmap(src) { decoder, info, _ ->
        decoder.allocator = ImageDecoder.ALLOCATOR_SOFTWARE
        val (tw, th) = fitWithin(info.size.width, info.size.height, 96 * 96)
        decoder.setTargetSize(tw, th)
    }
    val w = bmp.width; val h = bmp.height
    val px = IntArray(w * h)
    bmp.getPixels(px, 0, w, 0, 0, w, h)
    PendingImage(px, w, h)
} catch (e: Exception) { null }

private fun fitWithin(w: Int, h: Int, maxPx: Int): Pair<Int, Int> {
    if (w <= 0 || h <= 0) return 1 to 1
    if (w * h <= maxPx) return w to h
    val s = Math.sqrt(maxPx.toDouble() / (w.toDouble() * h))
    return (w * s).toInt().coerceAtLeast(1) to (h * s).toInt().coerceAtLeast(1)
}

@Composable
private fun LocalContextOrNull(): Context = androidx.compose.ui.platform.LocalContext.current
