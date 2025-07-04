#!/bin/bash
# Initialize MongoDB replica set for both local and Docker access

echo "Waiting for MongoDB to start..."
sleep 5

echo "Initializing replica set with hybrid configuration..."
docker exec -it mongodb mongosh --eval "
  try {
    rs.initiate({
      _id: 'rs0',
      members: [
        { 
          _id: 0, 
          host: '127.0.0.1:27017',
          priority: 1 
        }
      ]
    });
    print('Replica set initialized successfully');
  } catch (e) {
    if (e.codeName === 'AlreadyInitialized') {
      print('Replica set already initialized');
      // Try to reconfigure if needed
      var config = rs.conf();
      config.members[0].host = '127.0.0.1:27017';
      try {
        rs.reconfig(config, {force: true});
        print('Replica set reconfigured');
      } catch (e2) {
        print('Could not reconfigure: ' + e2);
      }
    } else {
      print('Error: ' + e);
    }
  }
"

echo "Checking replica set status..."
sleep 2
docker exec -it mongodb mongosh --eval "rs.status()"

echo "MongoDB replica set initialized!"
echo ""
echo "Connection strings:"
echo "  From host machine: mongodb://localhost:27017/?replicaSet=rs0&directConnection=true"
echo "  From Docker containers: mongodb://mongodb:27017/?replicaSet=rs0"