print = console.log;
document.addEventListener("DOMContentLoaded", () => {

    container = document.getElementById("container");
    ws = new WebSocket("ws://localhost:8800/ws");
    
ws.onmessage = function(e) {
    let newItem = document.createElement("div").appendChild(document.createElement("ul"));

    let data = JSON.parse(e.data);
    console.log(data);
    function createTree(data) { //recursion
        let li = document.createElement("li");
        let span = document.createElement("span");
        
        span.title = data.change;
        span.classList.add("tf-nc");

        span.classList.add("tag-" + data.tag?.toLowerCase());
        span.innerText = data.name;
        li.appendChild(span);
        if (data.children && data.children.length > 0) {
            let ul = document.createElement("ul");
            for (let child of data.children) {
                ul.appendChild(createTree(child));
            }
            li.appendChild(ul);
        }
        return li;
    }
    newItem.appendChild(createTree(data));
    newItem.className = "tf-tree";
    print(newItem);
    container.appendChild(newItem);

    }
});

