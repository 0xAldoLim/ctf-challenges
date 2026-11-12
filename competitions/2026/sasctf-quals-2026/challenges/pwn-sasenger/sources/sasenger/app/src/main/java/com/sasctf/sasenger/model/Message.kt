package com.sasctf.sasenger.model

import androidx.compose.runtime.mutableStateOf
import com.sasctf.sasenger.media.MessagePart

class Message(
    val id: String,
    val peer: String,
    val incoming: Boolean,
    val parts: List<MessagePart>,
    val ts: Long = System.currentTimeMillis(),
) {
    val deliveryState = mutableStateOf<String?>(null)
}
