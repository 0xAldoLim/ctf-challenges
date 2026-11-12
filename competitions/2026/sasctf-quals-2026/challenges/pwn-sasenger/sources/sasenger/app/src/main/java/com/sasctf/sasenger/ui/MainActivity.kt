package com.sasctf.sasenger.ui

import android.content.Intent
import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import androidx.navigation.compose.rememberNavController
import com.sasctf.sasenger.core.Repository
import com.sasctf.sasenger.ui.theme.SasengerTheme

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        handleProvisioning(intent)
        setContent {
            SasengerTheme {
                val nav = rememberNavController()
                val start = if (Repository.account.value != null) "home" else "auth"
                NavHost(navController = nav, startDestination = start) {
                    composable("auth") {
                        AuthScreen(onAuthed = {
                            nav.navigate("home") { popUpTo("auth") { inclusive = true } }
                        })
                    }
                    composable("home") {
                        HomeScreen(
                            onOpenChat = { peer -> nav.navigate("chat/$peer") },
                            onLogout = {
                                Repository.logout()
                                nav.navigate("auth") { popUpTo(0) }
                            })
                    }
                    composable("chat/{peer}") { entry ->
                        ChatScreen(
                            peer = entry.arguments?.getString("peer").orEmpty(),
                            onBack = { nav.popBackStack() })
                    }
                }
            }
        }
    }

    override fun onNewIntent(intent: Intent) {
        super.onNewIntent(intent)
        handleProvisioning(intent)
    }

    private fun handleProvisioning(intent: Intent?) {
        val relay = intent?.getStringExtra("relay") ?: return
        val user = intent.getStringExtra("username") ?: return
        val token = intent.getStringExtra("token") ?: return
        Repository.loginWithToken(relay, user, token, intent.getStringExtra("account_id") ?: "")
    }
}
