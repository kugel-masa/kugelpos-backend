#!/bin/bash
# Initialize MongoDB replica set for local development (outside Docker)
# This configures the replica set to use localhost instead of mongodb hostname

echo "Reconfiguring MongoDB replica set for local development..."

# Force reconfigure the replica set to use localhost
docker exec mongodb mongosh --quiet --eval "
  try {
    var config = rs.conf();
    config.members[0].host = 'localhost:27017';
    rs.reconfig(config, {force: true});
    print('✓ Replica set reconfigured for localhost:27017');
  } catch (e) {
    print('Error: ' + e.message);
    print('Trying to initialize new replica set...');
    try {
      rs.initiate({
        _id: 'rs0',
        members: [
          { _id: 0, host: 'localhost:27017', priority: 1 }
        ]
      });
      print('✓ New replica set initialized with localhost:27017');
    } catch (e2) {
      print('Failed to initialize: ' + e2.message);
    }
  }
"

echo ""
echo "Waiting for replica set to stabilize..."
sleep 3

echo "Checking replica set status..."
docker exec mongodb mongosh --quiet --eval "
  var status = rs.status();
  print('Replica set: ' + status.set);
  print('Primary host: ' + status.members[0].name);
  print('State: ' + (status.members[0].stateStr || 'UNKNOWN'));
"

echo ""
echo "MongoDB is now configured for local development!"
echo "Services can connect using: mongodb://localhost:27017/?replicaSet=rs0"