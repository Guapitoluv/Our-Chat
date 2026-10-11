import { 
    GetUsersMessage
} from "../../services/messages.js";

import { 
    WebSocketClient
} from "../../services/websocket.js";

const ws = new WebSocketClient(
        "wss://our-chat-1gz3.onrender.com/ws"
    );

await ws.connect();

const myUserId = "5802c72f-47d6-4ce6-88a2-f715d4a40888";

const response = await ws.request(new GetUsersMessage());
const contacts = (response.payload.users || []).filter(u => u.id !== myUserId);
                
console.log(contacts);