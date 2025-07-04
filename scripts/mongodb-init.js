// MongoDB initialization script for single-node replica set
// This script runs inside the MongoDB container

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
        host: "mongodb:27017"
      }
    ]
  });
  print("Replica set initialized");
}

// Wait for replica set to be ready
sleep(3000);

// Show status
printjson(rs.status());