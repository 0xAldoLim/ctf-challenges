package com.sasctf.sasenger.core

import java.io.ByteArrayOutputStream

object MessageContainer {
    private const val TAG_TEXT = 1
    private const val TAG_IMAGE = 2
    private const val TAG_STICKER = 3
    private const val TAG_REPLY = 4
    private const val BYTES_PER_PIXEL = 4

    class Builder {
        private val parts = ByteArrayOutputStream()
        private var count = 0

        fun reply(quote: String): Builder {
            val bytes = quote.toByteArray(Charsets.UTF_8)
            parts.u8(TAG_REPLY); parts.u32(bytes.size); parts.write(bytes)
            count++; return this
        }

        fun text(s: String): Builder {
            val bytes = s.toByteArray(Charsets.UTF_8)
            parts.u8(TAG_TEXT); parts.u32(bytes.size); parts.write(bytes)
            count++; return this
        }

        fun image(argb: IntArray, w: Int, h: Int): Builder {
            val rowBytes = w * BYTES_PER_PIXEL
            val data = ByteArrayOutputStream(argb.size * BYTES_PER_PIXEL)
            for (p in argb) { data.u8(p); data.u8(p ushr 8); data.u8(p ushr 16); data.u8(p ushr 24) }
            val bytes = data.toByteArray()
            parts.u8(TAG_IMAGE); parts.u16(w); parts.u16(h); parts.u32(rowBytes)
            parts.u32(bytes.size); parts.write(bytes)
            count++; return this
        }

        fun sticker(id: Int, palette: IntArray): Builder {
            parts.u8(TAG_STICKER); parts.u16(id); parts.u16(palette.size)
            for (c in palette) parts.u32(c)
            count++; return this
        }

        fun build(): ByteArray {
            val out = ByteArrayOutputStream()
            out.write("SMC1".toByteArray(Charsets.US_ASCII))
            out.u8(1); out.u8(0); out.u16(count)
            parts.writeTo(out)
            return out.toByteArray()
        }
    }

    fun text(s: String): ByteArray = Builder().text(s).build()
    fun image(argb: IntArray, w: Int, h: Int): ByteArray = Builder().image(argb, w, h).build()
    fun sticker(id: Int, palette: IntArray): ByteArray = Builder().sticker(id, palette).build()

    private fun ByteArrayOutputStream.u8(v: Int) { write(v and 0xff) }
    private fun ByteArrayOutputStream.u16(v: Int) { u8(v); u8(v ushr 8) }
    private fun ByteArrayOutputStream.u32(v: Int) { u16(v); u16(v ushr 16) }
}
