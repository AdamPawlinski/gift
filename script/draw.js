import * as clone from 'rfdc'
// const clone = require('rfdc')();

export default function draw(userTab) {
  let drawResult;
  let drawResultArr = [];
  let drawResultsState = [];
  
  let userTabStart = userTab.map(user => user);
  let drawUserTab = userTabStart.slice();
  if (userTabStart.length < 2) {
    console.warn('Too less users to make the draw');
  } else {
    for (let i of userTabStart) {
      if (drawUserTab.length === 1 && drawUserTab[0] === i) {
        drawUserTab = userTabStart.map(user => user).slice();
        draw();
        break;
      }
      do {
        drawResult = Math.floor(Math.random() * drawUserTab.length);
      } while (drawUserTab[drawResult].users === i);
      console.log('i', i)
      const drawUser = drawUserTab.splice(drawResult, 1).toString();
      drawResultArr.push({ [i]: drawUser });
    }
  }
  // ToDo: remove the localStorage result saving
  localStorage.setItem('draw', JSON.stringify(drawResultArr))
  drawResultsState = JSON.parse(localStorage.getItem('draw'))
  console.log(drawResultArr);
  return drawResultArr;
}