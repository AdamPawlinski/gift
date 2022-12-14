const clone = require('rfdc')();

let userTabStart = [
  "Adam",
  "Krzysztof",
  "Anna",
  "Grzegorz",
  "Karolina",
];

export default function draw() {  
  let drawResult;
  let drawResultArr = [];
  let drawResultsState = [];
  let drawUserTab = userTabStart.slice();
  console.log(drawUserTab);
  if (userTabStart.length < 2) {
    console.warn('Too less users to make the draw');
  } else {
    for (let i of userTabStart) {
      if (drawUserTab.length === 1 && drawUserTab[0] === i) {
        drawUserTab = userTabStart.slice();
        draw();
        break;
      }
      do {
        drawResult = Math.floor(Math.random() * drawUserTab.length);
      } while (drawUserTab[drawResult] === i);
      const drawUser = drawUserTab.splice(drawResult, 1).toString();
      drawResultArr.push({ [i]: drawUser });
    }
  }
  localStorage.setItem('draw', JSON.stringify(drawResultArr))
  drawResultsState = JSON.parse(localStorage.getItem('draw'))
  console.log(drawResultArr);
  return drawResultArr;
}