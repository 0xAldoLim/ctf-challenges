package com.sasctf.sasenger.service

import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.Service
import android.content.Context
import android.content.Intent
import android.content.pm.ServiceInfo
import android.os.Build
import android.os.IBinder
import com.sasctf.sasenger.core.Repository

class MessengerService : Service() {
    override fun onBind(intent: Intent?): IBinder? = null

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q)
            startForeground(1, notification(), ServiceInfo.FOREGROUND_SERVICE_TYPE_DATA_SYNC)
        else
            startForeground(1, notification())
        Repository.startPolling()
        return START_STICKY
    }

    private fun notification(): Notification {
        val chId = "sasenger"
        getSystemService(NotificationManager::class.java).createNotificationChannel(
            NotificationChannel(chId, "Sasenger", NotificationManager.IMPORTANCE_LOW))
        return Notification.Builder(this, chId)
            .setContentTitle("Sasenger")
            .setContentText("Connected")
            .setSmallIcon(android.R.drawable.ic_dialog_email)
            .build()
    }

    companion object {
        fun start(ctx: Context) {
            val i = Intent(ctx, MessengerService::class.java)
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) ctx.startForegroundService(i)
            else ctx.startService(i)
        }
    }
}
