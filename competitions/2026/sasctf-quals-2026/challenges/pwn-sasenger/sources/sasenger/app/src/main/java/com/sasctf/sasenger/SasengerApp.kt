package com.sasctf.sasenger

import android.app.Application
import com.sasctf.sasenger.core.Repository

class SasengerApp : Application() {
    override fun onCreate() {
        super.onCreate()
        Repository.init(this)
    }
}
