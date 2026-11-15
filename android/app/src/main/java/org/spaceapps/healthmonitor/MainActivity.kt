package org.spaceapps.healthmonitor

import android.content.ClipData
import android.content.ClipboardManager
import android.content.Context
import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.compose.setContent
import androidx.compose.foundation.Image
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.compose.ui.window.Dialog
import androidx.health.connect.client.HealthConnectClient
import androidx.health.connect.client.PermissionController
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch
import org.json.JSONObject
import java.time.Instant

// Palette taken from the team logo
val Accent = Color(0xFF005C96)   // steel blue outline
val Caution = Color(0xFFB86E00)
val Warning = Color(0xFFD81B1B)  // red "01"
val Ink = Color(0xFF17191F)
val Panel = Color(0xFFF1F5FB)

/**
 * HEALTH-01 phone app, kept simple on purpose: connect to a server, collect wearable data, count exercise reps.
 * Dashboards, alerts and the assistant live on the website / desktop app.
 */
class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        val state = AppState(applicationContext)
        val health = HealthConnectManager(applicationContext)
        setContent {
            MaterialTheme(colorScheme = lightColorScheme(primary = Accent, background = Color(0xFFFBFCFE), surface = Color.White, onBackground = Ink, onSurface = Ink)) {
                Surface(Modifier.fillMaxSize(), color = MaterialTheme.colorScheme.background) { Main(state, health) }
            }
        }
    }
}

private enum class Tab(val label: String, val icon: ImageVector) {
    CONNECT("Connect", Icons.Filled.Settings), HEALTH("Health", Icons.Filled.Favorite), EXERCISE("Exercise", Icons.Filled.Refresh)
}

@Composable
fun Main(state: AppState, health: HealthConnectManager) {
    var tab by remember { mutableStateOf(if (state.assigned) Tab.HEALTH else Tab.CONNECT) }
    // keep the pairing status fresh while the app is open (pending -> assigned shows up without a restart)
    LaunchedEffect(state.status) {
        while (state.status == "pending") { delay(5000); state.refresh() }
    }
    // Uploads granted Health Connect data while the app is open. Stops when the screen is left.
    LaunchedEffect(state.assigned, state.autoSync) {
        if (!state.autoSync || !state.assigned) return@LaunchedEffect
        while (true) {
            if (health.grantedPermissions().isNotEmpty()) state.lastSyncMessage = syncHealth(state, health)
            delay(5 * 60 * 1000)
        }
    }
    Box(Modifier.fillMaxSize()) {
    Scaffold(
        topBar = {
            Row(Modifier.fillMaxWidth().padding(16.dp, 12.dp), verticalAlignment = Alignment.CenterVertically) {
                Image(painterResource(R.drawable.team_logo), contentDescription = "Team logo", Modifier.size(36.dp))
                Spacer(Modifier.width(10.dp))
                Column(Modifier.weight(1f)) {
                    Text("HEALTH-01", fontWeight = FontWeight.Bold, fontSize = 18.sp)
                    Text(if (state.assigned) "Connected as ${state.callsign}" else state.status, fontSize = 12.sp,
                        color = if (state.assigned) Accent else Caution)
                }
            }
        },
        bottomBar = {
            NavigationBar {
                Tab.entries.forEach { t ->
                    NavigationBarItem(selected = tab == t, onClick = { tab = t }, icon = { Icon(t.icon, null) }, label = { Text(t.label) })
                }
            }
        },
        ) { pad ->
        Box(Modifier.padding(pad)) {
            when (tab) {
                Tab.CONNECT -> ConnectScreen(state)
                Tab.HEALTH -> HealthScreen(state, health)
                Tab.EXERCISE -> ExerciseScreen(state)
            }
        }
    }
        if (state.showTour) Walkthrough(onDone = { state.closeTour() })
    }
}

private val tourSteps = listOf(
    Triple("01", "Connect this phone", "Type the HEALTH-01 server address and tap Connect. Copy the device ID so someone can assign this phone to you on the Devices page."),
    Triple("02", "Health uploads itself", "Allow the Health Connect types you want. While the app is open and this phone is assigned, those readings upload about every 5 minutes. You can still sync by hand."),
    Triple("03", "Count reps on camera", "Exercise fills the screen. Blue lines follow your body. Pick a movement, tap Start, and the count is saved when you stop."),
)

@Composable
private fun Walkthrough(onDone: () -> Unit) {
    var step by remember { mutableIntStateOf(0) }
    val (code, title, body) = tourSteps[step]
    Dialog(onDismissRequest = onDone) {
        Column(Modifier.background(Color.White, RoundedCornerShape(16.dp)).padding(20.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
            Text(code, fontFamily = FontFamily.Monospace, fontSize = 12.sp, color = Color(0xFF1D2BDB))
            Text(title, fontSize = 26.sp, fontWeight = FontWeight.Bold, color = Ink)
            Text(body, color = Ink)
            Row(verticalAlignment = Alignment.CenterVertically) {
                Text("${step + 1} of ${tourSteps.size}", fontSize = 12.sp, color = Color.Gray)
                Spacer(Modifier.weight(1f))
                if (step > 0) OutlinedButton(onClick = { step-- }) { Text("Back") }
                Spacer(Modifier.width(8.dp))
                Button(onClick = { if (step < tourSteps.size - 1) step++ else onDone() }) {
                    Text(if (step < tourSteps.size - 1) "Next" else "Done")
                }
            }
        }
    }
}

/** Upload the last 14 days of granted Health Connect data. Returns a short status line. */
suspend fun syncHealth(state: AppState, health: HealthConnectManager): String = try {
    val (items, notes) = health.collect()
    if (items.isEmpty()) "No granted Health Connect data found." + notes.joinToString("; ", " ")
    else {
        var acc = 0; var upd = 0; var rej = 0
        items.chunked(500).forEach { c ->
            val r = state.api.upload(measurements = c)
            acc += r.getInt("accepted"); upd += r.getInt("updated"); rej += r.getInt("rejected")
        }
        "Uploaded $acc new, $upd updated, $rej rejected." + if (notes.isNotEmpty()) " Issues: ${notes.joinToString("; ")}" else ""
    }
} catch (e: Exception) { "Sync failed: ${e.message}" }

@Composable
fun Card(content: @Composable ColumnScope.() -> Unit) {
    ElevatedCard(Modifier.fillMaxWidth()) { Column(Modifier.padding(14.dp), verticalArrangement = Arrangement.spacedBy(6.dp), content = content) }
}

@Composable
fun ConnectScreen(state: AppState) {
    val scope = rememberCoroutineScope()
    val context = LocalContext.current
    var url by remember { mutableStateOf(state.serverUrl) }
    var busy by remember { mutableStateOf(false) }
    Column(Modifier.fillMaxSize().padding(16.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
        Card {
            Text("This phone's device ID", color = Accent)
            Text(state.deviceUuid, fontFamily = FontFamily.Monospace, fontSize = 15.sp)
            Text("Show this to the operator. They assign this phone to you on the Devices page.", fontSize = 12.sp, color = Color.Gray)
            TextButton(onClick = {
                (context.getSystemService(Context.CLIPBOARD_SERVICE) as ClipboardManager).setPrimaryClip(ClipData.newPlainText("device id", state.deviceUuid))
            }) { Text("Copy ID") }
        }
        Card {
            Text("Server", color = Accent)
            OutlinedTextField(url, { url = it }, label = { Text("Server address") }, singleLine = true,
                keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Uri), modifier = Modifier.fillMaxWidth())
            Text("Example: http://192.168.1.20:8080 (the computer running HEALTH-01). The emulator uses http://10.0.2.2:8000.", fontSize = 12.sp, color = Color.Gray)
            Button(enabled = !busy && url.startsWith("http"), onClick = {
                busy = true
                state.setServer(url)
                scope.launch {
                    try { state.connect() } catch (e: Exception) { state.lastMessage = "Could not connect: ${e.message}" }
                    busy = false
                }
            }) { Text(if (busy) "Connecting…" else "Connect") }
        }
        Card {
            Text("Status", color = Accent)
            val (label, color) = when (state.status) {
                "assigned" -> "Connected as ${state.callsign}" to Accent
                "pending" -> "Waiting for the operator to assign this phone" to Caution
                "revoked" -> "This phone was revoked. Ask the operator." to Warning
                else -> "Not connected" to Color.Gray
            }
            Text(label, color = color, fontWeight = FontWeight.SemiBold)
            state.lastMessage?.let { Text(it, fontSize = 12.sp, color = Color.Gray) }
            OutlinedButton(onClick = { scope.launch { state.refresh() } }) { Text("Check again") }
        }
        OutlinedButton(onClick = { state.openTour() }) { Text("Show the tour") }
    }
}

@Composable
fun HealthScreen(state: AppState, health: HealthConnectManager) {
    val scope = rememberCoroutineScope()
    var granted by remember { mutableStateOf(emptySet<String>()) }
    var message by remember { mutableStateOf<String?>(null) }
    var syncing by remember { mutableStateOf(false) }
    var fatigue by remember { mutableIntStateOf(3) }
    val launcher = rememberLauncherForActivityResult(PermissionController.createRequestPermissionResultContract()) { result ->
        granted = granted + result
        if (result.isNotEmpty() && state.autoSync && state.assigned) {
            scope.launch { message = syncHealth(state, health) }
        }
    }
    LaunchedEffect(Unit) { granted = health.grantedPermissions() }

    LazyColumn(contentPadding = PaddingValues(16.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
        item {
            Card {
                Text("Upload to the crew server", color = Accent)
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Text("Auto sync while the app is open", Modifier.weight(1f))
                    Switch(checked = state.autoSync, onCheckedChange = { state.updateAutoSync(it) })
                }
                Text("About every 5 minutes, after this phone is assigned and you have allowed a Health Connect type.", fontSize = 12.sp, color = Color.Gray)
                state.lastSyncMessage?.let { Text(it, fontSize = 12.sp, color = Color.Gray) }
                Button(enabled = !syncing && granted.isNotEmpty() && state.assigned, onClick = {
                    syncing = true
                    scope.launch { message = syncHealth(state, health); syncing = false }
                }) { Text(if (syncing) "Syncing…" else "Sync now") }
                if (!state.assigned) Text("Connect and get assigned first (Connect tab).", color = Caution, fontSize = 12.sp)
                message?.let { Text(it, fontSize = 12.sp, color = Color.Gray) }
            }
        }
        item {
            Card {
                Text("How tired are you? (Samn-Perelli 1–7)", color = Accent)
                Text("1 fully alert … 7 completely exhausted", fontSize = 12.sp, color = Color.Gray)
                Row(verticalAlignment = Alignment.CenterVertically) {
                    OutlinedButton(onClick = { if (fatigue > 1) fatigue-- }) { Text("−") }
                    Text("  $fatigue / 7  ", fontSize = 18.sp)
                    OutlinedButton(onClick = { if (fatigue < 7) fatigue++ }) { Text("+") }
                    Spacer(Modifier.width(12.dp))
                    Button(enabled = state.assigned, onClick = {
                        scope.launch {
                            val now = Instant.now()
                            val rec = JSONObject().put("metric", "fatigue_score").put("value", fatigue).put("unit", "score 1-7")
                                .put("timestamp", now.toString()).put("external_id", "and-fatigue-${now.epochSecond}")
                            message = try { state.api.upload(measurements = listOf(rec)); "Check-in saved." } catch (e: Exception) { e.message }
                        }
                    }) { Text("Send") }
                }
            }
        }
        item {
            Card {
                Text("Health Connect (read-only, per data type)", color = Accent)
                when (health.sdkStatus) {
                    HealthConnectClient.SDK_AVAILABLE -> Text("Available", fontSize = 12.sp, color = Color.Gray)
                    HealthConnectClient.SDK_UNAVAILABLE_PROVIDER_UPDATE_REQUIRED -> Text("Install or update Health Connect from Google Play.", color = Caution, fontSize = 12.sp)
                    else -> Text("Health Connect is not available on this device.", color = Caution, fontSize = 12.sp)
                }
            }
        }
        items(health.features) { f ->
            Card {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Column(Modifier.weight(1f)) { Text(f.title); Text(f.detail, fontSize = 12.sp, color = Color.Gray) }
                    if (f.permission in granted) Text("Allowed", color = Accent, fontSize = 12.sp)
                    else Button(enabled = health.isAvailable, onClick = { launcher.launch(setOf(f.permission)) }) { Text("Allow") }
                }
            }
        }
    }
}
