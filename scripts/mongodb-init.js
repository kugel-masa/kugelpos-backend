// MongoDB initialization script for single-node replica set.
//
// Runs inside the MongoDB container during the docker-entrypoint init phase,
// when mongod is bound to 127.0.0.1 only. We must therefore initiate the
// replica set with `host: "localhost:27017"` — using `mongodb:27017` here
// fails with NodeNotFound because the bound listener cannot reach its own
// container hostname during init. After init completes mongod restarts with
// --bind_ip_all, and the in-network `mongodb-init` sidecar (see
// docker-compose.mongodb-init.yaml) reconfigures the host to `mongodb:27017`
// so other containers can join the replica set.

// Wait for MongoDB to be ready
sleep(2000);

// Check if replica set is already initialized
try {
  var status = rs.status();
  print("Replica set already initialized");
} catch (e) {
  print("Initializing replica set...");
  rs.initiate({
    _id: "rs0",
    members: [
      {
        _id: 0,
        host: "localhost:27017"
      }
    ]
  });
  print("Replica set initialized");
}

// Wait for replica set to be ready
sleep(3000);

// Show status
printjson(rs.status());