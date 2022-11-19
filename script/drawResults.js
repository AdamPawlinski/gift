export default function showResults(drawResultArr, person) {  
  if (!drawResultArr)  {
    console.warn('Start lottery first')
    return
  }
  const result = drawResultArr.find(
    res => {
      return Object.keys(res).toString() === person
    }
  );
  let personPicked;
  if (result) {
    return personPicked = Object.values(result).toString();
  } else {
    return personPicked = "Nie znaleziono imienia";
  }
}