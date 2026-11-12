package com.sasctf.sasenger.media

class MessagePart(
    @JvmField val kind: Int,
    @JvmField val text: String?,
    @JvmField val width: Int,
    @JvmField val height: Int,
    @JvmField val pixels: IntArray?,
    @JvmField val stickerId: Int,
    @JvmField val palette: IntArray?,
) {
    companion object {
        const val KIND_TEXT = 0
        const val KIND_IMAGE = 1
        const val KIND_STICKER = 2
        const val KIND_REPLY = 3
    }
}
