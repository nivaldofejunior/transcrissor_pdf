db.createUser({
  user: "projetot_user",
  pwd: "nivaldo",
  roles: [
    {
      role: "readWrite",
      db: "projeto_t_db"
    }
  ]
});
