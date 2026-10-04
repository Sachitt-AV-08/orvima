const CMDS = {
  win: 'irm https://raw.githubusercontent.com/Sachitt-AV-08/orvima/main/install.ps1 | iex',
  unix: 'curl -fsSL https://raw.githubusercontent.com/Sachitt-AV-08/orvima/main/install.sh | sh',
};

const out = document.getElementById('installcmd');
document.querySelectorAll('.tab').forEach((tab) => {
  tab.addEventListener('click', () => {
    document.querySelectorAll('.tab').forEach((t) => t.classList.remove('active'));
    tab.classList.add('active');
    out.textContent = CMDS[tab.dataset.os];
  });
});